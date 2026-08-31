import SwiftUI
import PhotosUI

struct ChatView: View {
    /// When non-nil the view is presented as a sheet and shows a Done button.
    var onDismiss: (() -> Void)? = nil
    @State private var viewModel = ChatViewModel()
    @State private var photoItem: PhotosPickerItem?
    @State private var isHoldingMic = false
    @FocusState private var inputFocused: Bool

    var body: some View {
        NavigationStack {
            ZStack {
                Color.thukBG.ignoresSafeArea()

                VStack(spacing: 0) {
                    messageList
                    inputBar
                }
            }
            .navigationTitle("Chat")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if let onDismiss {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Done", action: onDismiss)
                            .foregroundStyle(Color.thukAccent)
                    }
                }
            }
        }
        .onChange(of: photoItem) { _, item in
            guard let item else { return }
            Task {
                if let data = try? await item.loadTransferable(type: Data.self) {
                    await viewModel.sendImage(data)
                }
                photoItem = nil
            }
        }
    }

    // MARK: - Message list

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 12) {
                    if viewModel.messages.isEmpty {
                        emptyState
                            .padding(.top, 60)
                    }
                    ForEach(viewModel.messages) { msg in
                        MessageBubble(message: msg)
                            .id(msg.id)
                    }
                    if viewModel.isLoading {
                        ThinkingBubble()
                    }
                    if let err = viewModel.errorMessage {
                        Text(err)
                            .font(.system(size: 13))
                            .foregroundStyle(Color.thukDanger)
                            .padding(.horizontal, 20)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 16)
            }
            .onChange(of: viewModel.messages.count) { _, _ in
                if let last = viewModel.messages.last {
                    withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                }
            }
        }
    }

    // MARK: - Input bar

    private var inputBar: some View {
        VStack(spacing: 0) {
            Divider().background(Color.thukSurfaceHi)

            HStack(alignment: .bottom, spacing: 10) {
                // Photo picker
                PhotosPicker(selection: $photoItem, matching: .images) {
                    Image(systemName: "camera")
                        .font(.system(size: 20, weight: .medium))
                        .foregroundStyle(Color.thukSecondary)
                        .frame(width: 36, height: 36)
                }

                // Text input
                ZStack(alignment: .leading) {
                    if viewModel.inputText.isEmpty {
                        Text("Message")
                            .font(.system(size: 16))
                            .foregroundStyle(Color.thukSecondary)
                            .padding(.horizontal, 12)
                    }
                    TextField("", text: $viewModel.inputText, axis: .vertical)
                        .font(.system(size: 16))
                        .foregroundStyle(.white)
                        .lineLimit(1...5)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                        .focused($inputFocused)
                        .submitLabel(.send)
                        .onSubmit { sendText() }
                }
                .background(Color.thukSurface)
                .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))

                // Send / Mic
                if !viewModel.inputText.isEmpty {
                    sendButton
                } else {
                    micButton
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(Color.thukBG)
        }
    }

    private var sendButton: some View {
        Button { sendText() } label: {
            Image(systemName: "arrow.up.circle.fill")
                .font(.system(size: 32))
                .foregroundStyle(Color.thukAccent)
        }
        .buttonStyle(.plain)
        .transition(.scale.combined(with: .opacity))
    }

    private var micButton: some View {
        Button {
            // tap does nothing — use long-press below
        } label: {
            Image(systemName: viewModel.isRecording ? "mic.fill" : "mic")
                .font(.system(size: 22, weight: .medium))
                .foregroundStyle(viewModel.isRecording ? Color.thukDanger : Color.thukSecondary)
                .frame(width: 36, height: 36)
                .scaleEffect(viewModel.isRecording ? 1.15 : 1.0)
                .animation(.easeInOut(duration: 0.2), value: viewModel.isRecording)
        }
        .buttonStyle(.plain)
        .simultaneousGesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in
                    if !viewModel.isRecording {
                        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                        viewModel.startRecording()
                    }
                }
                .onEnded { _ in
                    if viewModel.isRecording {
                        Task { await viewModel.stopRecordingAndSend() }
                    }
                }
        )
    }

    // MARK: - Empty state

    private var emptyState: some View {
        VStack(spacing: 12) {
            Text("Thuk")
                .font(.system(size: 32, weight: .heavy, design: .rounded))
                .foregroundStyle(.white)
            Text("Tell me what you spent.\nVoice, photo, or text — all work.")
                .font(.system(size: 15))
                .foregroundStyle(Color.thukSecondary)
                .multilineTextAlignment(.center)
        }
    }

    // MARK: - Helpers

    private func sendText() {
        guard !viewModel.inputText.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        Task { await viewModel.sendText() }
    }
}

// MARK: - Bubble components

private struct MessageBubble: View {
    let message: ChatMessage

    var isUser: Bool { message.role == .user }

    var body: some View {
        HStack {
            if isUser { Spacer(minLength: 60) }

            Text(message.content)
                .font(.system(size: 15))
                .foregroundStyle(isUser ? .white : .white)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(isUser ? Color.thukAccent : Color.thukSurface)
                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))

            if !isUser { Spacer(minLength: 60) }
        }
        .frame(maxWidth: .infinity, alignment: isUser ? .trailing : .leading)
    }
}

private struct ThinkingBubble: View {
    @State private var phase = 0

    var body: some View {
        HStack(spacing: 5) {
            ForEach(0..<3, id: \.self) { i in
                Circle()
                    .fill(Color.thukSecondary)
                    .frame(width: 7, height: 7)
                    .scaleEffect(phase == i ? 1.3 : 1.0)
                    .animation(
                        .easeInOut(duration: 0.4).repeatForever().delay(Double(i) * 0.15),
                        value: phase
                    )
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color.thukSurface)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .frame(maxWidth: .infinity, alignment: .leading)
        .onAppear { phase = 1 }
    }
}
