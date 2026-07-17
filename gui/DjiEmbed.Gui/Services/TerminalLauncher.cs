using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// Launches an interactive shell that lands the user on proof the CLI
/// works (#293): Windows Terminal when installed, classic PowerShell
/// otherwise, pre-running "dji-embed --help" so the first thing they see
/// is output, not a blank prompt.
/// </summary>
public static class TerminalLauncher
{
    private const string ProofCommand = "dji-embed --help";

    /// <summary>
    /// Candidate launches, best first. Pure so tests can assert the exact
    /// invocations without spawning shells.
    /// </summary>
    public static IReadOnlyList<ProcessStartInfo> Candidates(
        string workingDirectory)
    {
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

    /// <summary>Tries each candidate in order; false when none started.</summary>
    public static bool Launch()
    {
        var home = Environment.GetFolderPath(
            Environment.SpecialFolder.UserProfile);
        foreach (var psi in Candidates(home))
        {
            try
            {
                Process.Start(psi);
                return true;
            }
            catch (Exception e) when (e is Win32Exception
                or InvalidOperationException or PlatformNotSupportedException)
            {
                // Not installed on this machine — try the next one.
            }
        }
        return false;
    }
}
