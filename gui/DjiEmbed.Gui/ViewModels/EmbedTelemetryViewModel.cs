using System;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.Input;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>
/// The "Embed telemetry" flow: a folder of MP4+SRT in, new GPS-tagged
/// copies out. Originals are never modified — the done screen says so.
/// </summary>
public partial class EmbedTelemetryViewModel(
    string? cliPath, DjiEmbedRunner runner, Action goHome)
    : FlowViewModel(cliPath, runner, goHome)
{
    protected override string GenericFailureMessage =>
        "Something went wrong while embedding the flight data.";

    [RelayCommand]
    private async Task StartAsync(string folder)
    {
        if (!EnsureCli())
        {
            return;
        }
        if (!FolderInspector.Inspect(folder).HasVideos)
        {
            Fail("No videos (.MP4) were found in that folder. Pick the "
                 + "folder that holds the drone videos together with their "
                 + ".SRT flight logs.");
            return;
        }
        await ExecuteFlowAsync(() => RunStepAsync(
            "Embedding flight data into new copies…", ["embed", folder]));
    }
}
