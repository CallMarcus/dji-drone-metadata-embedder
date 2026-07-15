using System;
using System.Collections.ObjectModel;
using System.Text.Json;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>One row of the setup checklist.</summary>
public sealed record SetupItem(string Label, bool Present, string? Detail);

/// <summary>
/// "Check my setup": doctor as a novice-worded checklist. Missing tools
/// are a report (red row + hint), not a failure screen; only a crashed or
/// missing engine fails. Auto-started by the view.
/// </summary>
public partial class CheckSetupViewModel(
    string? cliPath, DjiEmbedRunner runner, Action goHome)
    : FlowViewModel(cliPath, runner, goHome)
{
    protected override string GenericFailureMessage =>
        "The setup check could not be completed.";

    [ObservableProperty]
    public partial bool AllGood { get; set; }

    public ObservableCollection<SetupItem> Items { get; } = [];

    [RelayCommand]
    private async Task StartAsync()
    {
        if (!EnsureCli())
        {
            return;
        }
        await ExecuteFlowAsync(async () =>
        {
            var result = await RunCliAsync("Checking…", ["doctor"]);
            if (result.ExitCode != 0
                || result.Terminal is not { Kind: ProgressEventKind.Result } t)
            {
                Fail(result.Terminal?.Message ?? GenericFailureMessage,
                    string.IsNullOrWhiteSpace(result.StderrText)
                        ? null : result.StderrText);
                return false;
            }
            Items.Clear();
            ParseTools(t.Summary);
            AllGood = t.Ok == true;
            return true;
        });
    }

    private void ParseTools(JsonElement? summary)
    {
        if (summary is not { ValueKind: JsonValueKind.Object } s
            || !s.TryGetProperty("tools", out var tools)
            || tools.ValueKind != JsonValueKind.Object)
        {
            return;
        }
        foreach (var tool in tools.EnumerateObject())
        {
            var present = tool.Value.TryGetProperty("present", out var p)
                          && p.ValueKind == JsonValueKind.True;
            var detail = present
                ? tool.Value.TryGetProperty("version", out var v)
                  && v.ValueKind == JsonValueKind.String
                    ? $"version {v.GetString()}" : null
                : "Reinstalling the application should restore this.";
            Items.Add(new SetupItem(FriendlyName(tool.Name), present, detail));
        }
    }

    private static string FriendlyName(string tool) => tool switch
    {
        "ffmpeg" => "Video tools (FFmpeg)",
        "exiftool" => "Photo tools (ExifTool)",
        _ => tool,
    };
}
