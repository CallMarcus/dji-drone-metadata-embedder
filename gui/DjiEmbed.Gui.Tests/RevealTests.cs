using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

// Reveal.For is the pure seam behind "Show in folder" — like
// TerminalLauncher.Candidates, tests assert the exact invocation
// without spawning a file manager.
public class RevealTests
{
    [Fact]
    public void Windows_select_argument_quotes_the_full_path()
    {
        Assert.Equal("/select,\"C:\\a b\\map.html\"",
            Reveal.SelectArgument("C:\\a b\\map.html"));
    }

    [Fact]
    public void Non_windows_reveal_opens_the_containing_directory()
    {
        if (OperatingSystem.IsWindows())
        {
            return; // the runtime branch under test is unreachable here
        }
        var psi = Reveal.For("/tmp/some dir/map.html");
        Assert.NotNull(psi);
        Assert.Equal("/tmp/some dir", psi.FileName);
        Assert.True(psi.UseShellExecute);
    }
}
