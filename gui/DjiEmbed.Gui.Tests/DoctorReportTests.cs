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

    [Fact]
    public void Missing_tool_gets_the_reinstall_hint()
    {
        var items = DoctorReport.Parse(Summary(
            """{"tools": {"exiftool": {"present": false}}}"""));
        var item = Assert.Single(items);
        Assert.Equal("Photo tools (ExifTool)", item.Label);
        Assert.False(item.Present);
        Assert.Contains("Reinstalling", item.Detail);
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
