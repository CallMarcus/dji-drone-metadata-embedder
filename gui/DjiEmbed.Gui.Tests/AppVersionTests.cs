using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

// #532: the main window title carries the stamped version so any field
// report screenshot names the build it came from. Dev builds (the SDK's
// default 1.0.0) show the bare name — a made-up number would mislead
// exactly the reports the title exists for.
public class AppVersionTests
{
    [Theory]
    [InlineData("2.11.0", "2.11.0")]
    [InlineData("2.11.0+abc1234", "2.11.0")]  // SourceLink build metadata
    [InlineData("2.12.0-rc.1", "2.12.0-rc.1")]
    public void Stamped_versions_survive_with_metadata_stripped(
        string informational, string expected)
    {
        Assert.Equal(expected, AppVersion.Normalize(informational));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData("1.0.0")]
    [InlineData("1.0.0+abc1234")]
    public void Unstamped_builds_normalize_to_null(string? informational)
    {
        Assert.Null(AppVersion.Normalize(informational));
    }

    [Fact]
    public void Title_carries_the_version_only_when_there_is_one()
    {
        Assert.Equal("DJI Metadata Embedder v2.11.0",
            AppVersion.TitleFor("2.11.0"));
        Assert.Equal("DJI Metadata Embedder", AppVersion.TitleFor(null));
    }

    [Fact]
    public void Window_title_is_always_presentable()
    {
        // The test host itself is an unstamped build, so this exercises
        // the real assembly-attribute path end to end.
        Assert.StartsWith("DJI Metadata Embedder", AppVersion.WindowTitle);
    }
}
