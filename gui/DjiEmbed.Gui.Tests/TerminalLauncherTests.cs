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
}
