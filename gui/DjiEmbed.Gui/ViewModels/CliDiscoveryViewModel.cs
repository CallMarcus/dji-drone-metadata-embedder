using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
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
public partial class CliDiscoveryViewModel(
    string? cliPath,
    Action goHome,
    Func<string?, Task<TerminalLaunchResult>>? launch = null)
    : ViewModelBase
{
    public const string DocsUrl =
        "https://callmarcus.github.io/dji-drone-metadata-embedder/";

    private readonly Func<string?, Task<TerminalLaunchResult>> _launch =
        launch ?? TerminalLauncher.LaunchAsync;

    /// <summary>
    /// Curated to show what the GUI deliberately can't do. Static strings —
    /// the live --help expander covers completeness.
    /// </summary>
    public IReadOnlyList<StarterCommand> StarterCommands { get; } =
        StarterCommandsFor(Platforms.Current);

    /// <summary>The opening revelation, phrased per platform.</summary>
    public string IntroText { get; } = IntroTextFor(Platforms.Current);

    /// <summary>How the CLI reaches a terminal differs per install: the
    /// Windows installer appends it to PATH, the macOS DMG keeps it inside
    /// the bundle, and Linux has no installer at all (#442).</summary>
    internal static string IntroTextFor(OSPlatform platform) =>
        platform == OSPlatform.Windows
            ? "Everything this app does — and a lot more — runs on the "
              + "dji-embed command line, and it is already installed: the "
              + "app's installer put it on your PATH. Open any terminal, "
              + "type dji-embed, and it just works."
        : platform == OSPlatform.OSX
            ? "Everything this app does — and a lot more — runs on the "
              + "dji-embed command line, and it is already installed: it "
              + "ships inside this app. The button below opens Terminal "
              + "ready to use it; the guide below shows how to make it "
              + "available in every terminal."
        : "Everything this app does — and a lot more — runs on the "
          + "dji-embed command line. Install it once with pipx "
          + "(pipx install dji-drone-metadata-embedder) and it works "
          + "in any terminal.";

    /// <summary>The examples are copy-paste bait, so the sample folder
    /// follows the OS — a D:\ drive path is Windows-only truth.</summary>
    internal static IReadOnlyList<StarterCommand> StarterCommandsFor(
        OSPlatform platform)
    {
        var footage = platform == OSPlatform.Windows ? @"D:\Footage"
            : platform == OSPlatform.OSX ? "~/Movies/Footage"
            : "~/Videos/Footage";
        return
        [
            new("dji-embed convert gpx flight.SRT",
                "Turn one flight log into a GPX track any mapping tool can read"),
            new($"dji-embed embed {footage} --redact fuzz",
                "Embed telemetry with the GPS positions fuzzed for privacy"),
            new($"dji-embed validate {footage}",
                "Check every video/flight-log pair for telemetry drift"),
            new("dji-embed doctor",
                "Full system diagnostics, beyond the app's setup check"),
        ];
    }

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
            HelpText = HelpFallbackFor(Platforms.Current, cliPath);
        }
    }

    /// <summary>
    /// The manual way to the command list when reading it failed. Only a
    /// user whose CLI is already misbehaving ever sees this, so the command
    /// it names has to be one their machine can actually run (#454).
    /// </summary>
    internal static string HelpFallbackFor(
        OSPlatform platform, string? cliPath) =>
        "The command list could not be loaded. Open a terminal and run  "
        + TerminalLauncher.ProofCommandFor(platform, cliPath)
        + "  to see it.";

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

    /// <summary>Why no terminal appeared; null when one did.</summary>
    [ObservableProperty]
    public partial string? TerminalMessage { get; set; }

    [RelayCommand]
    private async Task OpenTerminalAsync() =>
        TerminalMessage = TerminalMessageFor(
            await _launch(cliPath), Platforms.Current);

    /// <summary>
    /// What to say under the button when nothing opened. The refused-
    /// permission wording carries the way back out: macOS remembers Don't
    /// Allow, so without it the button is silently dead forever (#443).
    /// </summary>
    internal static string? TerminalMessageFor(
        TerminalLaunchResult result, OSPlatform platform) => result switch
    {
        TerminalLaunchResult.Started => null,
        TerminalLaunchResult.AutomationDenied =>
            "⚠️ macOS is blocking this app from opening Terminal. To allow "
            + "it, open System Settings > Privacy & Security > Automation, "
            + "find DJI Metadata Embedder in the list, and switch Terminal "
            + "back on. Then try this button again.",
        _ => platform == OSPlatform.OSX
            ? "⚠️ Terminal could not be opened. You can open it yourself — "
              + "the guide below shows how to reach the command line from "
              + "there."
            : platform == OSPlatform.Windows
            ? "⚠️ No terminal could be opened. Open PowerShell yourself and "
              + "enter  dji-embed --help  to see the same thing."
            : "⚠️ No terminal could be opened. Open your own and enter  "
              + "dji-embed --help  to see the same thing.",
    };

    [RelayCommand]
    private void OpenDocs() =>
        Process.Start(new ProcessStartInfo(DocsUrl) { UseShellExecute = true });

    [RelayCommand]
    private void GoHome() => goHome();
}
