using System;
using System.Collections.ObjectModel;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.ViewModels;

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
            foreach (var item in DoctorReport.Parse(t.Summary))
            {
                Items.Add(item);
            }
            AllGood = t.Ok == true;
            return true;
        });
    }
}
