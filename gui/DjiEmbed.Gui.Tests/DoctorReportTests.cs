using System.Runtime.InteropServices;
using System.Text.Json;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

public class DoctorReportTests
{
    private static JsonElement? Summary(string json) =>
        JsonDocument.Parse(json).RootElement.Clone();

    [Fact]
    public void Parses_present_tools_with_friendly_names_and_versions()
    {
        var items = DoctorReport.Parse(Summary(
            """{"tools": {"ffmpeg": {"present": true, "version": "7.1"}}}"""));
        var item = Assert.Single(items);
        Assert.Equal("Video tools (FFmpeg)", item.Label);
        Assert.True(item.Present);
        Assert.Equal("version 7.1", item.Detail);
    }

    // The Windows installer bundles both tools, so "reinstall" is right
    // there; the macOS app relies on Homebrew and must say so (#572).
    [Fact]
    public void Missing_tool_on_windows_gets_the_reinstall_hint()
    {
        var items = DoctorReport.Parse(Summary(
            """{"tools": {"exiftool": {"present": false}}}"""), OSPlatform.Windows);
        var item = Assert.Single(items);
        Assert.Equal("Photo tools (ExifTool)", item.Label);
        Assert.False(item.Present);
        Assert.Equal("Reinstalling the application should restore this.", item.Detail);
    }

    [Theory]
    [InlineData("exiftool", "Install it with Homebrew: brew install exiftool")]
    [InlineData("ffmpeg", "Install it with Homebrew: brew install ffmpeg")]
    public void Missing_tool_on_macos_names_the_homebrew_command(
        string tool, string expected)
    {
        var items = DoctorReport.Parse(Summary(
            $"{{\"tools\": {{\"{tool}\": {{\"present\": false}}}}}}"), OSPlatform.OSX);
        Assert.Equal(expected, Assert.Single(items).Detail);
    }

    [Fact]
    public void Missing_tool_elsewhere_points_at_the_package_manager()
    {
        var items = DoctorReport.Parse(Summary(
            """{"tools": {"exiftool": {"present": false}}}"""), OSPlatform.Linux);
        Assert.Equal("Install it with your package manager.", Assert.Single(items).Detail);
    }

    [Fact]
    public void Unknown_tools_keep_their_raw_name()
    {
        var items = DoctorReport.Parse(Summary(
            """{"tools": {"newtool": {"present": true}}}"""));
        var item = Assert.Single(items);
        Assert.Equal("newtool", item.Label);
        Assert.Null(item.Detail);
    }

    [Fact]
    public void Absent_or_malformed_summary_yields_no_items()
    {
        Assert.Empty(DoctorReport.Parse(null));
        Assert.Empty(DoctorReport.Parse(Summary("""{"other": 1}""")));
    }
}
