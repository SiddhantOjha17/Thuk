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
            .preferredColorScheme(.dark)
            .tint(.thukAccent)
        }
    }
}
