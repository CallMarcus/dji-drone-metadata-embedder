using System.Runtime.InteropServices;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

// Reveal.For is the pure seam behind "Show in folder" — like
// TerminalLauncher.Candidates, platform-parameterized so every
// platform's exact invocation is asserted on any CI host, without
// spawning file managers.
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
        var full = Path.GetFullPath("C:\\a b\\map.html");
        var psi = Reveal.For("C:\\a b\\map.html", OSPlatform.Windows);
        Assert.NotNull(psi);
        Assert.Equal("explorer.exe", psi.FileName);
        Assert.Equal(Reveal.SelectArgument(full), psi.Arguments);
        Assert.False(psi.UseShellExecute);
    }

    [Fact]
    public void Macos_reveal_asks_finder_to_select_the_file()
    {
        var full = Path.GetFullPath("/tmp/some dir/map.html");
        var psi = Reveal.For("/tmp/some dir/map.html", OSPlatform.OSX);
        Assert.NotNull(psi);
        Assert.Equal("open", psi.FileName);
        Assert.Equal(["-R", full], psi.ArgumentList);
        Assert.False(psi.UseShellExecute);
    }

    [Fact]
    public void Elsewhere_reveal_opens_the_containing_directory()
    {
        var full = Path.GetFullPath("/tmp/some dir/map.html");
        var psi = Reveal.For("/tmp/some dir/map.html", OSPlatform.Linux);
        Assert.NotNull(psi);
        Assert.Equal(Path.GetDirectoryName(full), psi.FileName);
        Assert.True(psi.UseShellExecute);
    }
}
