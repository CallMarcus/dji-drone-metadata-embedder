using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>One curated example command on the discovery screen.</summary>
public sealed record StarterCommand(string Command, string Description);

/// <summary>
/// The CLI discovery screen (#293): a read-only soft landing from the app
/// into the dji-embed command line for users who have outgrown the three
/// task cards. One shell-launch button, curated examples, the live --help
/// output — no settings, no new task flows (anti-bloat rules).
/// </summary>
public partial class CliDiscoveryViewModel(string? cliPath, Action goHome)
    : ViewModelBase
{
    public const string DocsUrl =
        "https://callmarcus.github.io/dji-drone-metadata-embedder/";

    /// <summary>
    /// Curated to show what the GUI deliberately can't do. Static strings —
    /// the live --help expander covers completeness.
    /// </summary>
    public IReadOnlyList<StarterCommand> StarterCommands { get; } =
    [
        new(@"dji-embed convert gpx flight.SRT",
            "Turn one flight log into a GPX track any mapping tool can read"),
        new(@"dji-embed embed D:\Footage --redact fuzz",
            "Embed telemetry with the GPS positions fuzzed for privacy"),
        new(@"dji-embed validate D:\Footage",
            "Check every video/flight-log pair for telemetry drift"),
        new("dji-embed doctor",
            "Full system diagnostics, beyond the app's setup check"),
    ];

    [ObservableProperty]
    public partial string? HelpText { get; set; }

    [ObservableProperty]
    public partial bool HelpExpanded { get; set; }

    private bool _helpRequested;

    // Expanding the "every command" section triggers the one-time load, so
    // nothing is spawned for users who never open it.
    partial void OnHelpExpandedChanged(bool value)
    {
        if (value)
        {
            _ = LoadHelpAsync();
        }
    }

    /// <summary>
    /// Fills the expander from the bundled CLI's own --help, so new
    /// commands appear with zero screen maintenance. DjiEmbedRunner is not
    /// used here: it appends --progress jsonl, and --help output is plain
    /// text, not the event contract.
    /// </summary>
    [RelayCommand]
    private async Task LoadHelpAsync()
    {
        if (_helpRequested)
        {
            return;
        }
        _helpRequested = true;
        if (cliPath is null)
        {
            HelpText = "The dji-embed engine could not be found next to "
                + "this app. Reinstalling the application should fix this.";
            return;
        }
        try
        {
            HelpText = await RunHelpAsync(cliPath);
        }
        catch (Exception)
        {
            HelpText = "The command list could not be loaded. Open a "
                + "terminal and run  dji-embed --help  to see it.";
        }
    }

    private static async Task<string> RunHelpAsync(string cliPath)
    {
        var psi = new ProcessStartInfo
        {
            FileName = cliPath,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        psi.ArgumentList.Add("--help");
        using var process = Process.Start(psi)
            ?? throw new InvalidOperationException("--help did not start");
        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync();
        var stdout = await stdoutTask;
        _ = await stderrTask;
        if (process.ExitCode != 0 || string.IsNullOrWhiteSpace(stdout))
        {
            throw new InvalidOperationException(
                $"--help exited {process.ExitCode}");
        }
        return stdout.Trim();
    }

    [RelayCommand]
    private void OpenTerminal() => TerminalLauncher.Launch();

    [RelayCommand]
    private void OpenDocs() =>
        Process.Start(new ProcessStartInfo(DocsUrl) { UseShellExecute = true });

    [RelayCommand]
    private void GoHome() => goHome();
}
