using System;
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
    string? cliPath, DjiEmbedRunner runner, Action goHome)
    : FlowViewModel(cliPath, runner, goHome)
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
            if (contents.HasPhotos && !await RunStepAsync(
                    "Mapping your photos…", ["photomap", folder, "-r"]))
            {
                return false;
            }
            return true;
        });
    }
}
