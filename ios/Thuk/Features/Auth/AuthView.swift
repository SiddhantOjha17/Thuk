import SwiftUI

struct AuthView: View {
    @Environment(APIClient.self) private var api
    @State private var mode: Mode = .login
    @State private var name    = ""
    @State private var email   = ""
    @State private var password = ""
    @State private var isLoading = false
    @State private var errorMessage: String?

    enum Mode { case login, register }

    var body: some View {
        ZStack {
            Color.thukBG.ignoresSafeArea()

            ScrollView {
                VStack(spacing: 0) {
                    // Wordmark
                    VStack(spacing: 6) {
                        Text("Thuk")
                            .font(.system(size: 42, weight: .heavy, design: .rounded))
                            .foregroundStyle(.white)
                        Text("Personal expense tracker")
                            .font(.system(size: 14, weight: .regular))
                            .foregroundStyle(Color.thukSecondary)
                    }
                    .padding(.top, 80)
                    .padding(.bottom, 48)

                    // Mode toggle
                    HStack(spacing: 0) {
                        ForEach([Mode.login, .register], id: \.self) { m in
                            Button {
                                withAnimation(.easeInOut(duration: 0.2)) { mode = m }
                            } label: {
                                Text(m == .login ? "Sign in" : "Create account")
                                    .font(.system(size: 14, weight: .semibold))
                                    .foregroundStyle(mode == m ? .white : Color.thukSecondary)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 10)
                                    .background(
                                        mode == m
                                        ? Color.thukSurfaceHi
                                        : Color.clear
                                    )
                                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(4)
                    .background(Color.thukSurface)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .padding(.horizontal, 24)

                    // Form
                    VStack(spacing: 12) {
                        if mode == .register {
                            ThukTextField(placeholder: "Your name", text: $name, icon: "person")
                                .transition(.opacity.combined(with: .move(edge: .top)))
                        }
                        ThukTextField(placeholder: "Email", text: $email, icon: "envelope",
                                      keyboardType: .emailAddress)
                        ThukTextField(placeholder: "Password", text: $password, icon: "lock",
                                      isSecure: true)
                    }
                    .padding(.horizontal, 24)
                    .padding(.top, 20)
                    .animation(.easeInOut(duration: 0.2), value: mode)

                    // Error
                    if let msg = errorMessage {
                        Text(msg)
                            .font(.system(size: 13))
                            .foregroundStyle(Color.thukDanger)
                            .padding(.top, 12)
                            .padding(.horizontal, 24)
                    }

                    // CTA
                    PrimaryButton(
                        title: mode == .login ? "Sign in" : "Create account",
                        isLoading: isLoading
                    ) { submit() }
                    .padding(.horizontal, 24)
                    .padding(.top, 24)
                }
            }
        }
    }

    private func submit() {
        errorMessage = nil
        isLoading = true
        Task {
            do {
                if mode == .login {
                    try await login()
                } else {
                    try await register()
                }
            } catch let err as APIError {
                errorMessage = err.errorDescription
            } catch {
                errorMessage = "Something went wrong."
            }
            isLoading = false
        }
    }

    private func login() async throws {
        struct Body: Encodable { let email, password: String }
        let tokens: TokenResponse = try await api.request(
            "/auth/login", method: "POST", body: Body(email: email, password: password)
        )
        api.storeTokens(tokens, name: email, email: email)
        await api.fetchAndStoreProfile()
    }

    private func register() async throws {
        guard !name.trimmingCharacters(in: .whitespaces).isEmpty else {
            errorMessage = "Please enter your name."; return
        }
        struct Body: Encodable { let name, email, password: String }
        let tokens: TokenResponse = try await api.request(
            "/auth/register", method: "POST",
            body: Body(name: name, email: email, password: password)
        )
        api.storeTokens(tokens, name: name, email: email)
    }
}

// MARK: - Text field component

private struct ThukTextField: View {
    let placeholder: String
    @Binding var text: String
    let icon: String
    var keyboardType: UIKeyboardType = .default
    var isSecure: Bool = false

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(Color.thukSecondary)
                .frame(width: 20)

            if isSecure {
                SecureField(placeholder, text: $text)
                    .font(.system(size: 16))
                    .foregroundStyle(.white)
            } else {
                TextField(placeholder, text: $text)
                    .font(.system(size: 16))
                    .foregroundStyle(.white)
                    .keyboardType(keyboardType)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(keyboardType == .emailAddress ? .never : .words)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .background(Color.thukSurface)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}
