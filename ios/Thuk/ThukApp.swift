import SwiftUI

@main
struct ThukApp: App {
    @State private var api = APIClient.shared

    var body: some Scene {
        WindowGroup {
            Group {
                if api.isAuthenticated {
                    RootView()
                } else {
                    AuthView()
                }
            }
            .environment(api)
            .overlay(alignment: .top) {
                if api.isWakingServer {
                    Text("Waking up the server… this can take up to 30s")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(Color.black.opacity(0.75), in: Capsule())
                        .padding(.top, 8)
                        .transition(.move(edge: .top).combined(with: .opacity))
                        .animation(.easeInOut(duration: 0.25), value: api.isWakingServer)
                }
            }
            .preferredColorScheme(.dark)
            .tint(Color.thukAccent)
        }
    }
}
