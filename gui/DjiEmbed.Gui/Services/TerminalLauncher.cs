using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading.Tasks;

namespace DjiEmbed.Gui.Services;

/// <summary>How a terminal launch ended. The refused-permission case is
/// separate because it is the only one with a way back out (#443).</summary>
public enum TerminalLaunchResult
{
    /// <summary>A terminal opened.</summary>
    Started,

    /// <summary>macOS refused this app permission to drive Terminal.</summary>
    AutomationDenied,

    /// <summary>No terminal opened, for any other reason.</summary>
    Failed,
}

/// <summary>
/// Launches an interactive shell that lands the user on proof the CLI
/// works (#293): on Windows, Windows Terminal when installed and classic
/// PowerShell otherwise; on macOS, Terminal.app via osascript. Both
/// pre-run "dji-embed --help" so the first thing the user sees is
/// output, not a blank prompt.
/// </summary>
public static class TerminalLauncher
{
    /// <summary>errAEEventNotPermitted, as osascript prints it. macOS
    /// translates the message around it but never the number.</summary>
    private const string AppleEventsDenied = "(-1743)";

    private const string ProofCommand = "dji-embed --help";

    /// <summary>What the launch button should say — the shell it will
    /// actually open on this platform.</summary>
    public static string ButtonLabel => ButtonLabelOn(Platforms.Current);

    internal static string ButtonLabelOn(OSPlatform platform) =>
        platform == OSPlatform.Windows ? "Open PowerShell and try it"
        : platform == OSPlatform.OSX ? "Open Terminal and try it"
        : "Open a terminal and try it";

    /// <summary>Candidate launches for this machine, best first.</summary>
    public static IReadOnlyList<ProcessStartInfo> Candidates(
        string workingDirectory, string? cliPath = null) =>
        Candidates(workingDirectory, Platforms.Current, cliPath);

    /// <summary>
    /// Candidate launches for a platform, best first. Pure so tests can
    /// assert every platform's exact invocations on any CI host without
    /// spawning shells. On macOS the proof command runs the bundled CLI
    /// by absolute path when known — the DMG install touches no PATH, so
    /// the bare command would land on "command not found" (#442); on
    /// Windows the installer's PATH entry makes the bare command the
    /// proof the discovery screen promises.
    /// </summary>
    internal static IReadOnlyList<ProcessStartInfo> Candidates(
        string workingDirectory, OSPlatform platform, string? cliPath = null)
    {
        if (platform == OSPlatform.OSX)
        {
            var proof = cliPath is null
                ? ProofCommand
                : $"{ShellSingleQuote(cliPath)} --help";

            // Terminal.app is always present and its windows stay open on
            // their own; "do script" opens a fresh window running the
            // proof command in the requested folder, and the second -e
            // brings Terminal in front of our window.
            var osa = new ProcessStartInfo("osascript")
            {
                UseShellExecute = false,
                WorkingDirectory = workingDirectory,
                // The consent prompt is answered after osascript has
                // already started, so this stream carries the only word
                // of a refusal (#443).
                RedirectStandardError = true,
            };
            osa.ArgumentList.Add("-e");
            osa.ArgumentList.Add(
                "tell application \"Terminal\" to do script "
                + AppleScriptString(
                    $"cd {ShellSingleQuote(workingDirectory)} && {proof}"));
            osa.ArgumentList.Add("-e");
            osa.ArgumentList.Add("tell application \"Terminal\" to activate");
            return [osa];
        }

        if (platform != OSPlatform.Windows)
        {
            // No dependable cross-distro terminal invocation (#360);
            // Launch reports false and the view's copy already names
            // any terminal.
            return [];
        }

        // wt.exe resolves through the App Execution Alias when Windows
        // Terminal is installed; a missing alias throws at Start and the
        // loop falls through to powershell.exe.
        var wt = new ProcessStartInfo("wt.exe")
        {
            UseShellExecute = true,
            WorkingDirectory = workingDirectory,
        };
        wt.ArgumentList.Add("-d");
        wt.ArgumentList.Add(workingDirectory);
        wt.ArgumentList.Add("powershell");
        wt.ArgumentList.Add("-NoExit");
        wt.ArgumentList.Add("-Command");
        wt.ArgumentList.Add(ProofCommand);

        var ps = new ProcessStartInfo("powershell.exe")
        {
            UseShellExecute = true,
            WorkingDirectory = workingDirectory,
        };
        ps.ArgumentList.Add("-NoExit");
        ps.ArgumentList.Add("-Command");
        ps.ArgumentList.Add(ProofCommand);

        return [wt, ps];
    }

    /// <summary>
    /// Tries each candidate in order and reports what the user will see.
    /// Starting is not the same as succeeding on macOS: osascript starts
    /// cleanly and only then asks permission to drive Terminal, so a
    /// refusal arrives on its error stream after the fact (#443).
    /// </summary>
    public static async Task<TerminalLaunchResult> LaunchAsync(
        string? cliPath = null)
    {
        var home = Environment.GetFolderPath(
            Environment.SpecialFolder.UserProfile);
        foreach (var psi in Candidates(home, cliPath))
        {
            Process? process;
            try
            {
                process = Process.Start(psi);
            }
            catch (Exception e) when (e is Win32Exception
                or InvalidOperationException or PlatformNotSupportedException)
            {
                // Not installed on this machine — try the next one.
                continue;
            }
            if (!psi.RedirectStandardError)
            {
                // A shell we handed a window to: it belongs to the user now
                // and waiting on it would never return. A null Process here
                // means the shell reused a running instance, which is still
                // a window on screen — not a reason to open a second one.
                process?.Dispose();
                return TerminalLaunchResult.Started;
            }
            if (process is null)
            {
                continue;
            }
            using (process)
            {
                // osascript returns as soon as Terminal has been told, so
                // this wait is short — and it lasts exactly as long as the
                // consent prompt, which keeps the button busy meanwhile.
                var stderr = await process.StandardError.ReadToEndAsync();
                await process.WaitForExitAsync();
                return ClassifyOsascript(process.ExitCode, stderr);
            }
        }
        return TerminalLaunchResult.Failed;
    }

    /// <summary>Reads an osascript run's outcome from what it left behind.
    /// Pure so the refusal path can be tested off a Mac.</summary>
    internal static TerminalLaunchResult ClassifyOsascript(
        int exitCode, string stderr) =>
        exitCode == 0 ? TerminalLaunchResult.Started
        : stderr.Contains(AppleEventsDenied, StringComparison.Ordinal)
            ? TerminalLaunchResult.AutomationDenied
            : TerminalLaunchResult.Failed;

    /// <summary>POSIX single-quoting: '…' with embedded ' as '\''.</summary>
    private static string ShellSingleQuote(string s) =>
        "'" + s.Replace("'", @"'\''") + "'";

    /// <summary>An AppleScript string literal: "…" with \ and " escaped.</summary>
    private static string AppleScriptString(string s) =>
        "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
}
