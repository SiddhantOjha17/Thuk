/// Thuk Share Extension
///
/// Appears in the iOS share sheet when the user shares any image.
/// Immediately uploads the image to the Thuk backend — no extra taps.
///
/// Flow:
///   User taps share → taps Thuk → this sheet appears → auto-uploads → auto-dismisses.

import SwiftUI
import UniformTypeIdentifiers
import Security

final class ShareViewController: UIViewController {

    // MARK: - State

    private enum UploadState {
        case uploading
        case success
        case error(String)
    }

    private var uploadState: UploadState = .uploading {
        didSet { updateUI() }
    }

    // MARK: - UI

    private var hostingController: UIHostingController<AnyView>?

    override func viewDidLoad() {
        super.viewDidLoad()

        // Semi-transparent background behind the card
        view.backgroundColor = UIColor.black.withAlphaComponent(0.45)

        let tap = UITapGestureRecognizer(target: self, action: #selector(backgroundTapped))
        tap.delegate = self
        view.addGestureRecognizer(tap)

        embedCard()
        Task { await loadAndUpload() }
    }

    private func embedCard() {
        let card = ShareCard(state: .uploading, onDismiss: { [weak self] in
            self?.finish()
        })
        let host = UIHostingController(rootView: AnyView(card))
        host.view.backgroundColor = .clear
        host.view.translatesAutoresizingMaskIntoConstraints = false
        addChild(host)
        view.addSubview(host.view)
        NSLayoutConstraint.activate([
            host.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            host.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            host.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])
        host.didMove(toParent: self)
        hostingController = host
    }

    private func updateUI() {
        let state = uploadState
        hostingController?.rootView = AnyView(
            ShareCard(state: state, onDismiss: { [weak self] in self?.finish() })
        )
    }

    @objc private func backgroundTapped() {
        finish()
    }

    private func finish() {
        extensionContext?.completeRequest(returningItems: [])
    }

    // MARK: - Upload

    private func loadAndUpload() async {
        // 1. Extract image from share context
        guard let imageData = await extractImageData() else {
            uploadState = .error("No image found.")
            return
        }

        // 2. Read auth token from shared Keychain
        guard let token = SharedKeychain.get("access_token") else {
            uploadState = .error("Not signed in to Thuk.")
            return
        }

        // 3. Upload
        do {
            try await uploadImage(imageData, token: token)
            uploadState = .success
            // Auto-dismiss after showing success briefly
            try? await Task.sleep(for: .seconds(1.5))
            finish()
        } catch {
            uploadState = .error("Upload failed. Try again from the app.")
        }
    }

    private func extractImageData() async -> Data? {
        guard
            let item     = extensionContext?.inputItems.first as? NSExtensionItem,
            let provider = item.attachments?.first(where: {
                $0.hasItemConformingToTypeIdentifier(UTType.image.identifier)
            })
        else { return nil }

        return await withCheckedContinuation { continuation in
            provider.loadItem(forTypeIdentifier: UTType.image.identifier) { result, _ in
                var data: Data?
                if let url   = result as? URL   { data = try? Data(contentsOf: url) }
                else if let img = result as? UIImage { data = img.jpegData(compressionQuality: 0.85) }
                else if let raw = result as? Data    { data = raw }
                continuation.resume(returning: data)
            }
        }
    }

    private func uploadImage(_ data: Data, token: String) async throws {
        let url      = URL(string: "https://thuk-production.up.railway.app/api/chat/image")!
        let boundary = UUID().uuidString

        var request        = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"receipt.jpg\"\r\n")
        body.append("Content-Type: image/jpeg\r\n\r\n")
        body.append(data)
        body.append("\r\n--\(boundary)--\r\n")
        request.httpBody = body

        let (_, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else {
            throw URLError(.badServerResponse)
        }
    }
}

// MARK: - Gesture delegate (only dismiss on background tap, not card tap)

extension ShareViewController: UIGestureRecognizerDelegate {
    func gestureRecognizer(_ gr: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool {
        touch.view == view
    }
}

// MARK: - Shared Keychain (duplicated here so extension has no dependency on main app)

private enum SharedKeychain {
    private static let service     = "com.yourname.thuk"
    private static let accessGroup = "group.com.yourname.thuk"

    static func get(_ key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String:           kSecClassGenericPassword,
            kSecAttrService as String:     service,
            kSecAttrAccount as String:     key,
            kSecAttrAccessGroup as String: accessGroup,
            kSecReturnData as String:      true,
            kSecMatchLimit as String:      kSecMatchLimitOne,
        ]
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
}

// MARK: - SwiftUI card UI

private struct ShareCard: View {
    let state: ShareViewController.UploadState
    let onDismiss: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            // Drag handle
            Capsule()
                .fill(Color.white.opacity(0.2))
                .frame(width: 36, height: 4)
                .padding(.top, 10)
                .padding(.bottom, 16)

            HStack(spacing: 16) {
                statusIcon
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(.white)
                    Text(subtitle)
                        .font(.system(size: 13))
                        .foregroundStyle(.white.opacity(0.6))
                }
                Spacer()
                if case .error = state {
                    Button("Dismiss", action: onDismiss)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(Color(hex: "6366F1"))
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 28)
        }
        .background(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(Color(hex: "1C1C1E"))
                .ignoresSafeArea(edges: .bottom)
        )
        .animation(.easeInOut(duration: 0.25), value: title)
    }

    @ViewBuilder
    private var statusIcon: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color(hex: "6366F1").opacity(0.15))
                .frame(width: 44, height: 44)
            switch state {
            case .uploading:
                ProgressView()
                    .tint(Color(hex: "6366F1"))
            case .success:
                Image(systemName: "checkmark")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(Color(hex: "10B981"))
            case .error:
                Image(systemName: "xmark")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(Color(hex: "F43F5E"))
            }
        }
    }

    private var title: String {
        switch state {
        case .uploading: "Processing receipt..."
        case .success:   "Added to Thuk"
        case .error:     "Could not upload"
        }
    }

    private var subtitle: String {
        switch state {
        case .uploading: "Extracting transaction details"
        case .success:   "Expense logged successfully"
        case .error(let msg): msg
        }
    }
}

// MARK: - Helpers

private extension Data {
    mutating func append(_ string: String) {
        if let data = string.data(using: .utf8) { append(data) }
    }
}

private extension Color {
    init(hex: String) {
        var s = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        if s.count == 3 { s = s.flatMap { [$0, $0] }.map(String.init).joined() }
        var n: UInt64 = 0
        Scanner(string: s).scanHexInt64(&n)
        self.init(
            .sRGB,
            red:   Double((n >> 16) & 0xFF) / 255,
            green: Double((n >>  8) & 0xFF) / 255,
            blue:  Double( n        & 0xFF) / 255
        )
    }
}
