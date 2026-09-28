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

    /// True while retrying a request that failed because the backend container
    /// looked asleep/cold (connection refused, timeout, or 502/503/504). The UI
    /// can observe this to show "waking up the server…" instead of a hard error.
    var isWakingServer: Bool = false

    private var accessToken: String?
    private var refreshToken: String?

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase

        // Try multiple ISO8601 formats to handle:
        // - "2026-08-31T12:39:38.735011Z"  (with Z + fractional)
        // - "2026-08-31T12:39:38Z"          (with Z, no fractional)
        // - "2026-08-31T12:39:38.735011"    (no timezone)
        // - "2026-08-31"                    (date only)
        let formatters: [ISO8601DateFormatter] = [
            { let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]; return f }(),
            { let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]; return f }(),
            { let f = ISO8601DateFormatter(); f.formatOptions = [.withFullDate, .withTime, .withColonSeparatorInTime, .withFractionalSeconds]; return f }(),
            { let f = ISO8601DateFormatter(); f.formatOptions = [.withFullDate]; return f }(),
        ]
        d.dateDecodingStrategy = .custom { decoder in
            let s = try decoder.singleValueContainer().decode(String.self)
            for fmt in formatters {
                if let date = fmt.date(from: s) { return date }
            }
            throw DecodingError.dataCorrupted(.init(
                codingPath: decoder.codingPath,
                debugDescription: "Cannot parse date: \(s)"
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
        let (data, response) = try await sendWithWakeupRetry(req)
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

        let (respData, response) = try await sendWithWakeupRetry(request)
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

        let (data, response) = try await sendWithWakeupRetry(req)

        guard let http = response as? HTTPURLResponse else { throw APIError.noData }

        if http.statusCode == 401 && retry {
            if let newToken = try? await sharedRefresh() {
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

    // Concurrent 401s (e.g. Home's summary/recent/budget fetched via `async let`) must not
    // each call /auth/refresh independently — the backend rotates the refresh token on use,
    // so a losing concurrent call gets an already-revoked token, fails, and used to trigger
    // a `logout()` that wiped the tokens a winning sibling had just written. Coalesce into
    // one in-flight refresh that everyone awaits.
    private var refreshTask: Task<String, Error>?

    private func sharedRefresh() async throws -> String {
        if let existing = refreshTask {
            return try await existing.value
        }
        let task = Task { try await doRefresh() }
        refreshTask = task
        defer { refreshTask = nil }
        return try await task.value
    }

    private func doRefresh() async throws -> String {
        guard let rt = refreshToken else { throw APIError.unauthorized }

        struct RefreshBody: Encodable { let refreshToken: String }
        guard let refreshURL = URL(string: kBaseURL.absoluteString + "/auth/refresh") else { throw APIError.unauthorized }
        var req = URLRequest(url: refreshURL)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try encoder.encode(RefreshBody(refreshToken: rt))

        let (data, response) = try await sendWithWakeupRetry(req)
        guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else {
            throw APIError.unauthorized
        }
        let tokens = try decoder.decode(TokenResponse.self, from: data)
        Keychain.set(tokens.accessToken,  key: "access_token")
        Keychain.set(tokens.refreshToken, key: "refresh_token")
        refreshToken = tokens.refreshToken
        return tokens.accessToken
    }

    // MARK: - Cold-start resilience
    //
    // Railway containers that scaled to zero can take 20-40s to come back up.
    // While cold, requests fail as connection-refused/timeout, or the edge
    // proxy answers with 502/503/504 before the app is listening. Retry those
    // specific failures with backoff instead of surfacing a raw error on the
    // very first attempt.

    private static let wakeupRetryDelays: [UInt64] = [2, 3, 5, 8, 8] // seconds; ~26s total

    private func sendWithWakeupRetry(_ request: URLRequest) async throws -> (Data, URLResponse) {
        var lastError: Error = URLError(.cannotConnectToHost)

        for attempt in 0...Self.wakeupRetryDelays.count {
            do {
                let (data, response) = try await URLSession.shared.data(for: request)
                if let http = response as? HTTPURLResponse,
                   [502, 503, 504].contains(http.statusCode),
                   attempt < Self.wakeupRetryDelays.count {
                    lastError = APIError.serverError(http.statusCode)
                } else {
                    isWakingServer = false
                    return (data, response)
                }
            } catch let error as URLError where Self.isColdStartError(error) {
                lastError = error
            } catch {
                isWakingServer = false
                throw APIError.network(error)
            }

            guard attempt < Self.wakeupRetryDelays.count else { break }
            isWakingServer = true
            try? await Task.sleep(nanoseconds: Self.wakeupRetryDelays[attempt] * 1_000_000_000)
        }

        isWakingServer = false
        throw APIError.network(lastError)
    }

    private static func isColdStartError(_ error: URLError) -> Bool {
        switch error.code {
        case .cannotConnectToHost, .networkConnectionLost, .timedOut, .cannotFindHost:
            return true
        default:
            // e.g. .notConnectedToInternet — a real local connectivity problem,
            // retrying won't help and would just delay the error uselessly.
            return false
        }
    }
}

// MARK: - Helpers

private struct EmptyResponse: Codable {}
private struct ErrorBody: Decodable { let detail: String }
