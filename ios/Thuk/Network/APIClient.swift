import Foundation

// MARK: - Configuration
// Change this to your deployed backend URL.
private let kBaseURL = URL(string: "https://thuk-production.up.railway.app")!

// MARK: - APIClient

@Observable
final class APIClient {
    static let shared = APIClient()

    var isAuthenticated: Bool = false
    var currentUserName: String = ""
    var currentUserEmail: String = ""

    private var accessToken: String?
    private var refreshToken: String?

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let isoShort = ISO8601DateFormatter()
        isoShort.formatOptions = [.withFullDate]
        d.dateDecodingStrategy = .custom { decoder in
            let s = try decoder.singleValueContainer().decode(String.self)
            if let d = iso.date(from: s) { return d }
            if let d = isoShort.date(from: s) { return d }
            throw DecodingError.dataCorrupted(.init(
                codingPath: decoder.codingPath,
                debugDescription: "Invalid date: \(s)"
            ))
        }
        return d
    }()

    private let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        return e
    }()

    init() {
        accessToken    = Keychain.get("access_token")
        refreshToken   = Keychain.get("refresh_token")
        currentUserName  = Keychain.get("user_name") ?? ""
        currentUserEmail = Keychain.get("user_email") ?? ""
        isAuthenticated  = accessToken != nil
    }

    // MARK: - Auth helpers

    func storeTokens(_ tokens: TokenResponse, name: String, email: String) {
        accessToken   = tokens.accessToken
        refreshToken  = tokens.refreshToken
        currentUserName  = name
        currentUserEmail = email
        Keychain.set(tokens.accessToken,  key: "access_token")
        Keychain.set(tokens.refreshToken, key: "refresh_token")
        Keychain.set(name,  key: "user_name")
        Keychain.set(email, key: "user_email")
        isAuthenticated = true
    }

    func logout() {
        accessToken   = nil
        refreshToken  = nil
        currentUserName  = ""
        currentUserEmail = ""
        Keychain.clearAll()
        isAuthenticated = false
    }

    // MARK: - Generic request

    func request<T: Decodable>(
        _ path: String,
        method: String = "GET",
        body: Encodable? = nil
    ) async throws -> T {
        let result: T = try await performRequest(path, method: method, body: body, retry: true)
        return result
    }

    /// Request variant that expects no response body (204)
    func requestNoBody(_ path: String, method: String, body: Encodable? = nil) async throws {
        let _: EmptyResponse = try await performRequest(path, method: method, body: body, retry: true)
    }

    /// Download raw bytes (e.g. CSV export)
    func requestRawData(_ path: String) async throws -> Data {
        guard let url = URL(string: kBaseURL.absoluteString + path) else { throw APIError.noData }
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        if let token = accessToken {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else {
            throw APIError.serverError((response as? HTTPURLResponse)?.statusCode ?? 0)
        }
        return data
    }

    // MARK: - Multipart upload

    func uploadVoice(_ audioData: Data) async throws -> ChatResponse {
        try await uploadFile(audioData, path: "/api/chat/voice", mimeType: "audio/m4a", filename: "voice.m4a")
    }

    func uploadImage(_ imageData: Data) async throws -> ChatResponse {
        try await uploadFile(imageData, path: "/api/chat/image", mimeType: "image/jpeg", filename: "receipt.jpg")
    }

    private func uploadFile(_ data: Data, path: String, mimeType: String, filename: String) async throws -> ChatResponse {
        let boundary = UUID().uuidString
        var request = URLRequest(url: kBaseURL.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        if let token = accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        body.append(data)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body

        let (respData, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.noData }
        guard 200..<300 ~= http.statusCode else {
            throw APIError.serverError(http.statusCode)
        }
        return try decoder.decode(ChatResponse.self, from: respData)
    }

    // MARK: - Private helpers

    private func performRequest<T: Decodable>(
        _ path: String,
        method: String,
        body: Encodable?,
        retry: Bool
    ) async throws -> T {
        guard let url = URL(string: kBaseURL.absoluteString + path) else {
            throw APIError.noData
        }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = accessToken {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body { req.httpBody = try encoder.encode(body) }

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await URLSession.shared.data(for: req)
        } catch {
            throw APIError.network(error)
        }

        guard let http = response as? HTTPURLResponse else { throw APIError.noData }

        if http.statusCode == 401 && retry {
            if let newToken = try? await doRefresh() {
                accessToken = newToken
                return try await performRequest(path, method: method, body: body, retry: false)
            }
            logout()
            throw APIError.unauthorized
        }

        if http.statusCode == 409 {
            let msg = (try? decoder.decode(ErrorBody.self, from: data))?.detail ?? "Conflict"
            throw APIError.conflict(msg)
        }

        guard 200..<300 ~= http.statusCode else {
            throw APIError.serverError(http.statusCode)
        }

        // 204 No Content — return EmptyResponse
        if data.isEmpty || http.statusCode == 204 {
            guard let empty = EmptyResponse() as? T else { throw APIError.noData }
            return empty
        }

        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingFailed(error)
        }
    }

    private func doRefresh() async throws -> String {
        guard let rt = refreshToken else { throw APIError.unauthorized }

        struct RefreshBody: Encodable { let refreshToken: String }
        var req = URLRequest(url: kBaseURL.appendingPathComponent("/auth/refresh"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try encoder.encode(RefreshBody(refreshToken: rt))

        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else {
            throw APIError.unauthorized
        }
        let tokens = try decoder.decode(TokenResponse.self, from: data)
        Keychain.set(tokens.accessToken,  key: "access_token")
        Keychain.set(tokens.refreshToken, key: "refresh_token")
        refreshToken = tokens.refreshToken
        return tokens.accessToken
    }
}

// MARK: - Helpers

private struct EmptyResponse: Codable {}
private struct ErrorBody: Decodable { let detail: String }
