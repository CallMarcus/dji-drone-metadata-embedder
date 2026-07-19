using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

public class CommandLineTests
{
    [Fact]
    public void Prefixes_the_program_and_leaves_simple_args_bare()
    {
        Assert.Equal("dji-embed flightmap /footage -r",
            CommandLine.Format("dji-embed", ["flightmap", "/footage", "-r"]));
    }

    [Fact]
    public void Quotes_args_that_contain_spaces()
    {
        Assert.Equal("dji-embed flightmap \"/my footage/june\" -r",
            CommandLine.Format("dji-embed", ["flightmap", "/my footage/june", "-r"]));
    }

    [Fact]
    public void Quotes_an_empty_arg_so_it_is_not_swallowed()
    {
        Assert.Equal("dji-embed check \"\"",
            CommandLine.Format("dji-embed", ["check", ""]));
    }

    [Fact]
    public void No_args_is_just_the_program()
    {
        Assert.Equal("dji-embed", CommandLine.Format("dji-embed", []));
    }

    [Fact]
    public void Quotes_an_arg_containing_a_tab_whitespace_is_not_just_spaces()
    {
        Assert.Equal("dji-embed x \"a\tb\"",
            CommandLine.Format("dji-embed", ["x", "a\tb"]));
    }

    [Fact]
    public void Passes_an_embedded_double_quote_through_verbatim_display_only_not_shell_safe()
    {
        // No whitespace ⇒ unquoted; the embedded quote is left as-is. This
        // documents that Format is display quoting, not shell escaping.
        Assert.Equal("dji-embed check a\"b",
            CommandLine.Format("dji-embed", ["check", "a\"b"]));
    }
}
