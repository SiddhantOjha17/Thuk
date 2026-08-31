import SwiftUI

struct RootView: View {
    @Environment(APIClient.self) private var api
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            HomeView()
                .tabItem { Label("Home",     systemImage: "house") }
                .tag(0)

            ChatView()
                .tabItem { Label("Chat",     systemImage: "bubble.left") }
                .tag(1)

            ExpenseListView()
                .tabItem { Label("Expenses", systemImage: "list.bullet") }
                .tag(2)

            InsightsView()
                .tabItem { Label("Insights", systemImage: "chart.pie") }
                .tag(3)

            WalletView()
                .tabItem { Label("Wallet",   systemImage: "wallet.bifold") }
                .tag(4)
        }
        .toolbarBackground(Color.thukSurface, for: .tabBar)
        .toolbarBackground(.visible, for: .tabBar)
    }
}
