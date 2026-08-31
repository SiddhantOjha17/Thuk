import Foundation
import AVFoundation

struct ChatMessage: Identifiable {
    enum Role { case user, assistant }
    let id = UUID()
    let role: Role
    let content: String
    let timestamp = Date.now
}

@Observable
final class ChatViewModel: NSObject, AVAudioRecorderDelegate {

    var messages: [ChatMessage] = []
    var inputText: String = ""
    var isLoading = false
    var isRecording = false
    var errorMessage: String?

    private var recorder: AVAudioRecorder?
    private var recordingURL: URL?
    private let api = APIClient.shared

    // MARK: - Text message

    func sendText() async {
        let text = inputText.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return }
        inputText = ""
        await send(userText: text) {
            struct Body: Encodable { let text: String }
            return try await self.api.request("/api/chat/message", method: "POST", body: Body(text: text))
        }
    }

    // MARK: - Voice

    func startRecording() {
        let session = AVAudioSession.sharedInstance()
        do {
            try session.setCategory(.record, mode: .default)
            try session.setActive(true)

            let url = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString + ".m4a")
            let settings: [String: Any] = [
                AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
                AVSampleRateKey: 44_100,
                AVNumberOfChannelsKey: 1,
                AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue,
            ]
            recorder = try AVAudioRecorder(url: url, settings: settings)
            recorder?.delegate = self
            recorder?.record()
            recordingURL = url
            isRecording = true
        } catch {
            errorMessage = "Microphone unavailable."
        }
    }

    func stopRecordingAndSend() async {
        recorder?.stop()
        isRecording = false
        guard let url = recordingURL else { return }
        defer { try? FileManager.default.removeItem(at: url) }

        guard let audioData = try? Data(contentsOf: url) else {
            errorMessage = "Could not read recording."
            return
        }

        await send(userText: "Voice message") {
            try await self.api.uploadVoice(audioData)
        }
        recordingURL = nil
    }

    // MARK: - Image

    func sendImage(_ data: Data) async {
        await send(userText: "Receipt / screenshot") {
            try await self.api.uploadImage(data)
        }
    }

    // MARK: - Shared send logic

    private func send(userText: String, request: @escaping () async throws -> ChatResponse) async {
        messages.append(.init(role: .user, content: userText))
        isLoading = true
        errorMessage = nil
        do {
            let response = try await request()
            messages.append(.init(role: .assistant, content: response.response))
            // If the agent added/edited/deleted an expense, notify all views to reload
            let lower = response.response.lowercased()
            if lower.contains("added") || lower.contains("deleted") || lower.contains("updated") {
                notifyDataChanged()
            }
        } catch let e as APIError {
            errorMessage = e.errorDescription
        } catch {
            errorMessage = "Something went wrong."
        }
        isLoading = false
    }
}
