using System;
using System.Diagnostics;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.Input;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>
/// The "Make a map" flow: folder in → progress → one result screen. Runs
/// flightmap and/or photomap (decided by <see cref="FolderInspector"/>)
/// through the bundled CLI and collects the map files it names.
/// </summary>
public partial class MakeMapViewModel(
    string? cli, DjiEmbedRunner runner, MapServer mapServer, Action goHome)
    : FlowViewModel(cli, runner, goHome)
{
    protected override string GenericFailureMessage =>
        "Something went wrong while making the map.";

    [RelayCommand]
    private async Task StartAsync(string folder)
    {
        if (!EnsureCli())
        {
            return;
        }
        var contents = FolderInspector.Inspect(folder);
        if (contents is { HasFlightLogs: false, HasPhotos: false })
        {
            Fail("No drone flight logs (.SRT) or photos were found in that "
                 + "folder. Pick the folder that contains your footage — "
                 + "subfolders are included automatically.");
            return;
        }
        await ExecuteFlowAsync(async () =>
        {
            if (contents.HasFlightLogs && !await RunStepAsync(
                    "Mapping your flights…", ["flightmap", folder, "-r"]))
            {
                return false;
            }
            // --link-originals: the map is written inside the mapped folder,
            // so the relative links are stable there — and they are what
            // powers the embedded 360° panorama viewer (#305).
            if (contents.HasPhotos && !await RunStepAsync(
                    "Mapping your photos…",
                    ["photomap", folder, "-r", "--link-originals"]))
            {
                return false;
            }
            return true;
        });
    }

    /// <summary>
    /// HTML maps open through a managed local server instead of file://,
    /// which blocks the 360° panorama viewer (#305). A server that fails
    /// to start falls back to the plain file open — the map minus the
    /// pano viewer, never nothing.
    /// </summary>
    protected override async Task OpenOutputCoreAsync(string path)
    {
        if (CliPath is not null
            && path.EndsWith(".html", StringComparison.OrdinalIgnoreCase))
        {
            var url = await mapServer.GetUrlAsync(CliPath, path);
            if (url is not null)
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
                return;
            }
        }
        await base.OpenOutputCoreAsync(path);
    }
}
