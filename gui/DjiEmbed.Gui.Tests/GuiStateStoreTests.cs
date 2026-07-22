using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

public class GuiStateStoreTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-statestore-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private string StatePath => Path.Combine(_dir, "state.json");

    private string MakeFolder(string name)
    {
        var folder = Path.Combine(_dir, name);
        Directory.CreateDirectory(folder);
        return folder;
    }

    [Fact]
    public void Loads_existing_state_at_construction()
    {
        GuiState.Save(GuiState.Empty.WithRecent("a"), StatePath);
        Assert.Equal(["a"], new GuiStateStore(StatePath).State.RecentFolders);
    }

    [Fact]
    public void PushRecent_saves_immediately()
    {
        var folder = MakeFolder("flight");
        new GuiStateStore(StatePath).PushRecent(folder);
        // A crash after the push must not lose the list — the file
        // already holds it.
        Assert.Equal([folder], GuiState.Load(StatePath).RecentFolders);
    }

    [Fact]
    public void SaveWindow_saves_immediately()
    {
        new GuiStateStore(StatePath)
            .SaveWindow(new WindowBounds(1, 2, 900, 700, false));
        Assert.Equal(new WindowBounds(1, 2, 900, 700, false),
            GuiState.Load(StatePath).Window);
    }

    [Fact]
    public void Saving_drops_recents_whose_folder_is_gone()
    {
        var kept = MakeFolder("kept");
        var doomed = MakeFolder("doomed");
        var store = new GuiStateStore(StatePath);
        store.PushRecent(doomed);
        store.PushRecent(kept);
        Directory.Delete(doomed);

        store.SaveWindow(new WindowBounds(0, 0, 900, 700, false));

        Assert.Equal([kept], GuiState.Load(StatePath).RecentFolders);
    }

    [Fact]
    public void ExistingRecents_hides_dead_paths_without_saving()
    {
        var kept = MakeFolder("kept");
        var doomed = MakeFolder("doomed");
        var store = new GuiStateStore(StatePath);
        store.PushRecent(doomed);
        store.PushRecent(kept);
        Directory.Delete(doomed);

        Assert.Equal([kept], store.ExistingRecents());
    }

    [Fact]
    public void Ephemeral_store_never_touches_disk()
    {
        var store = GuiStateStore.Ephemeral();
        store.PushRecent(MakeFolder("flight"));
        store.SaveWindow(new WindowBounds(0, 0, 900, 700, false));
        // Only the folder this test created — no state file anywhere.
        Assert.Equal(["flight"],
            Directory.GetFileSystemEntries(_dir).Select(Path.GetFileName));
    }
}
