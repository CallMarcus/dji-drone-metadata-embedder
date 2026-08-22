using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>
/// Window shell: one long-lived workspace page (GUI 2.0 spec 2026-07-18);
/// the read-only CLI discovery screen is the only other page.
/// </summary>
public partial class MainViewModel : ViewModelBase
{
    [ObservableProperty]
    public partial ViewModelBase CurrentPage { get; set; }

    // App-lifetime map server pool: repeated runs reuse running servers.
    // No dispose hook needed — each server child exits when its stdin pipe
    // closes, i.e. when this process ends (MapServer docs).
    private readonly MapServer _mapServer = new();

    private readonly WorkspaceViewModel _workspace;

    public MainViewModel(GuiStateStore? store = null)
    {
        _workspace = new WorkspaceViewModel(
            CliLocator.Find(), new DjiEmbedRunner(), _mapServer,
            OpenCliDiscovery, CliLocator.Find, stateStore: store);
        CurrentPage = _workspace;
    }

    /// <summary>The launch update note (#319): started by the app shell
    /// once the window exists, never by construction — tests build this
    /// view model freely and must not spawn the CLI as a side effect.</summary>
    public Task StartUpdateCheckAsync() => _workspace.CheckForUpdatesAsync();

    private void OpenCliDiscovery() => CurrentPage =
        new CliDiscoveryViewModel(CliLocator.Find(),
            () => CurrentPage = _workspace);
}
