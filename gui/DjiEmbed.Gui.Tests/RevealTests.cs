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
    public void Windows_reveal_asks_explorer_to_select_the_file()
    {
        Assert.SkipWhen(!OperatingSystem.IsWindows(),
            "Reveal.For only takes the explorer.exe branch on Windows");

        var full = Path.GetFullPath("C:\\a b\\map.html");
        var psi = Reveal.For("C:\\a b\\map.html");
        Assert.NotNull(psi);
        Assert.Equal("explorer.exe", psi.FileName);
        Assert.Equal(Reveal.SelectArgument(full), psi.Arguments);
        Assert.False(psi.UseShellExecute);
    }

    [Fact]
    public void Non_windows_reveal_opens_the_containing_directory()
    {
        Assert.SkipWhen(OperatingSystem.IsWindows(),
            "Reveal.For only takes the containing-directory branch off Windows");

        var psi = Reveal.For("/tmp/some dir/map.html");
        Assert.NotNull(psi);
        Assert.Equal("/tmp/some dir", psi.FileName);
        Assert.True(psi.UseShellExecute);
    }
}
