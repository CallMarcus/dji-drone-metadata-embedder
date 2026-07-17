using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

public class TerminalLauncherTests
{
    [Fact]
    public void Prefers_windows_terminal_then_falls_back_to_powershell()
    {
        var candidates = TerminalLauncher.Candidates(@"C:\Users\demo");

        Assert.Equal(2, candidates.Count);
        Assert.Equal("wt.exe", candidates[0].FileName);
        Assert.Equal("powershell.exe", candidates[1].FileName);
    }

    [Fact]
    public void Every_candidate_stays_open_and_proves_the_cli_works()
    {
        foreach (var psi in TerminalLauncher.Candidates(@"C:\Users\demo"))
        {
            Assert.Contains("-NoExit", psi.ArgumentList);
            Assert.Contains("dji-embed --help", psi.ArgumentList);
            Assert.Equal(@"C:\Users\demo", psi.WorkingDirectory);
        }
    }

    [Fact]
    public void Windows_terminal_opens_in_the_requested_folder()
    {
        var wt = TerminalLauncher.Candidates(@"C:\Users\demo")[0];
        var args = wt.ArgumentList.ToList();
        var d = args.IndexOf("-d");
        Assert.True(d >= 0 && args[d + 1] == @"C:\Users\demo");
    }
}
