using System.Runtime.InteropServices;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

// Candidates is the pure seam behind "Open PowerShell/Terminal and try
// it" — platform-parameterized so every platform's exact invocations are
// asserted on any CI host, without spawning shells.
public class TerminalLauncherTests
{
    [Fact]
    public void Windows_prefers_windows_terminal_then_falls_back_to_powershell()
    {
        var candidates = TerminalLauncher.Candidates(
            @"C:\Users\demo", OSPlatform.Windows);

        Assert.Equal(2, candidates.Count);
        Assert.Equal("wt.exe", candidates[0].FileName);
        Assert.Equal("powershell.exe", candidates[1].FileName);
    }

    [Fact]
    public void Every_windows_candidate_stays_open_and_proves_the_cli_works()
    {
        foreach (var psi in TerminalLauncher.Candidates(
                     @"C:\Users\demo", OSPlatform.Windows))
        {
            Assert.Contains("-NoExit", psi.ArgumentList);
            Assert.Contains("dji-embed --help", psi.ArgumentList);
            Assert.Equal(@"C:\Users\demo", psi.WorkingDirectory);
        }
    }

    [Fact]
    public void Windows_terminal_opens_in_the_requested_folder()
    {
        var wt = TerminalLauncher.Candidates(
            @"C:\Users\demo", OSPlatform.Windows)[0];
        var args = wt.ArgumentList.ToList();
        var d = args.IndexOf("-d");
        Assert.True(d >= 0 && args[d + 1] == @"C:\Users\demo");
    }

    [Fact]
    public void Macos_tells_terminal_to_prove_the_cli_then_come_to_front()
    {
        var candidates = TerminalLauncher.Candidates(
            "/Users/demo", OSPlatform.OSX);

        var osa = Assert.Single(candidates);
        Assert.Equal("osascript", osa.FileName);

        // Terminal windows stay open on their own; the do-script lands
        // the user in the requested folder with proof the CLI works,
        // and the activate brings Terminal in front of our window.
        var args = osa.ArgumentList.ToList();
        var doScript = Assert.Single(args, a => a.Contains("do script"));
        Assert.Contains("dji-embed --help", doScript);
        Assert.Contains("cd '/Users/demo'", doScript);
        Assert.Contains(args, a => a.Contains(
            "tell application \"Terminal\" to activate"));
    }

    [Fact]
    public void Macos_proof_command_runs_the_bundled_cli_when_its_path_is_known()
    {
        // #442: nothing puts dji-embed on PATH on macOS, so the bare
        // proof command lands a DMG-only user on "command not found".
        // With the bundled CLI's location known, the do-script runs it
        // by absolute path (single-quoted — the bundle name has spaces).
        var osa = Assert.Single(TerminalLauncher.Candidates(
            "/Users/demo", OSPlatform.OSX,
            "/Applications/DJI Metadata Embedder.app/Contents/MacOS/dji-embed"));

        var doScript = osa.ArgumentList.Single(a => a.Contains("do script"));
        Assert.Contains(
            "'/Applications/DJI Metadata Embedder.app/Contents/MacOS/dji-embed'"
            + " --help", doScript);
        Assert.DoesNotContain(" dji-embed --help", doScript);
    }

    [Fact]
    public void Windows_candidates_ignore_the_cli_path()
    {
        // The installer put dji-embed on PATH — the bare command is the
        // proof the sentence promises, so a known CLI path changes nothing.
        var bare = TerminalLauncher.Candidates(
            @"C:\Users\demo", OSPlatform.Windows);
        var withPath = TerminalLauncher.Candidates(
            @"C:\Users\demo", OSPlatform.Windows,
            @"C:\Program Files\DjiEmbed\dji-embed.exe");

        Assert.Equal(bare.Count, withPath.Count);
        for (var i = 0; i < bare.Count; i++)
        {
            Assert.Equal(bare[i].FileName, withPath[i].FileName);
            Assert.Equal(bare[i].ArgumentList, withPath[i].ArgumentList);
        }
    }

    [Fact]
    public void Macos_do_script_survives_a_folder_with_a_single_quote()
    {
        var osa = Assert.Single(TerminalLauncher.Candidates(
            "/Users/o'brien", OSPlatform.OSX));

        // Two escaping layers stack: the shell sees cd '/Users/o'\''brien',
        // and the AppleScript string literal wrapping it doubles the
        // backslash on the way in.
        var doScript = osa.ArgumentList.Single(a => a.Contains("do script"));
        Assert.Contains(@"cd '/Users/o'\\''brien'", doScript);
    }

    [Fact]
    public void Linux_has_no_candidates_yet()
    {
        // No dependable cross-distro terminal invocation (#360); Launch
        // reports false and the view's copy already names any terminal.
        Assert.Empty(TerminalLauncher.Candidates("/home/demo", OSPlatform.Linux));
    }

    [Fact]
    public void The_button_label_names_the_shell_the_platform_will_open()
    {
        Assert.Equal("Open PowerShell and try it",
            TerminalLauncher.ButtonLabelOn(OSPlatform.Windows));
        Assert.Equal("Open Terminal and try it",
            TerminalLauncher.ButtonLabelOn(OSPlatform.OSX));
        Assert.Equal("Open a terminal and try it",
            TerminalLauncher.ButtonLabelOn(OSPlatform.Linux));
    }

    [Fact]
    public void Macos_candidate_captures_the_error_stream()
    {
        // #443: osascript starts fine and fails asynchronously, so its
        // stderr and exit code are the only evidence the tell was refused.
        var osa = Assert.Single(TerminalLauncher.Candidates(
            "/Users/demo", OSPlatform.OSX));

        Assert.True(osa.RedirectStandardError);
        Assert.False(osa.UseShellExecute);
    }

    [Fact]
    public void A_clean_osascript_run_reports_started()
    {
        Assert.Equal(TerminalLaunchResult.Started,
            TerminalLauncher.ClassifyOsascript(0, string.Empty));
    }

    [Fact]
    public void A_refused_apple_event_reports_automation_denied()
    {
        // What Don't Allow on the automation consent prompt produces.
        Assert.Equal(TerminalLaunchResult.AutomationDenied,
            TerminalLauncher.ClassifyOsascript(1,
                "execution error: Not authorized to send Apple events to "
                + "Terminal. (-1743)\n"));
    }

    [Fact]
    public void A_refused_apple_event_is_recognised_in_any_language()
    {
        // macOS localizes the message but never the error number, so the
        // number is what the check hangs on.
        Assert.Equal(TerminalLaunchResult.AutomationDenied,
            TerminalLauncher.ClassifyOsascript(1,
                "Fehler beim Ausführen: Keine Berechtigung, Apple-Events an "
                + "\"Terminal\" zu senden. (-1743)\n"));
    }

    [Fact]
    public void Other_osascript_errors_are_ordinary_failures()
    {
        // Not a permission problem — pointing the user at System Settings
        // would send them somewhere that cannot help.
        Assert.Equal(TerminalLaunchResult.Failed,
            TerminalLauncher.ClassifyOsascript(1,
                "execution error: Terminal got an error: Application isn't "
                + "running. (-600)\n"));
    }
}
