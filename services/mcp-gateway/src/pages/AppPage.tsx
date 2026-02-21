import Header from "@/components/Header";

const AppPage = () => {
  return (
    <div className="noise-overlay min-h-screen bg-background text-foreground">
      <Header />
      <main className="flex items-center justify-center min-h-screen">
        <div className="text-center space-y-4">
          <h1 className="text-3xl font-bold tracking-tight">
            App Shell — <span className="text-[#0FF984]">V2 Coming Soon</span>
          </h1>
          <p className="text-muted-foreground text-lg">
            The Voco V2 cognitive engine is being wired up.
          </p>
        </div>
      </main>
    </div>
  );
};

export default AppPage;
