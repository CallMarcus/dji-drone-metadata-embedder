using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

// Parsing of single --progress jsonl lines (docs/progress_jsonl.schema.json).
public class ProgressEventTests
{
    [Fact]
    public void Parses_start_event()
    {
        var e = ProgressEvent.Parse(
            """{"v": 1, "event": "start", "command": "flightmap", "total": 3}""");
        Assert.NotNull(e);
        Assert.Equal(ProgressEventKind.Start, e!.Kind);
        Assert.Equal("flightmap", e.Command);
        Assert.Equal(3, e.Total);
    }

    [Fact]
    public void Parses_progress_event()
    {
        var e = ProgressEvent.Parse(
            """{"v": 1, "event": "progress", "current": 2, "total": 5, "item": "DJI_0002.SRT"}""");
        Assert.Equal(ProgressEventKind.Progress, e!.Kind);
        Assert.Equal(2, e.Current);
        Assert.Equal(5, e.Total);
        Assert.Equal("DJI_0002.SRT", e.Item);
    }

    [Fact]
    public void Parses_warning_event()
    {
        var e = ProgressEvent.Parse(
            """{"v": 1, "event": "warning", "message": "No GPS data", "item": "x.jpg"}""");
        Assert.Equal(ProgressEventKind.Warning, e!.Kind);
        Assert.Equal("No GPS data", e.Message);
        Assert.Equal("x.jpg", e.Item);
    }

    [Fact]
    public void Parses_result_event_with_outputs()
    {
        var e = ProgressEvent.Parse(
            """{"v": 1, "event": "result", "ok": true, "outputs": ["a.html", "b.kml"], "summary": {"flights": 2}}""");
        Assert.Equal(ProgressEventKind.Result, e!.Kind);
        Assert.True(e.Ok);
        Assert.Equal(new[] { "a.html", "b.kml" }, e.Outputs);
    }

    [Fact]
    public void Parses_error_event()
    {
        var e = ProgressEvent.Parse(
            """{"v": 1, "event": "error", "message": "No .SRT telemetry files found"}""");
        Assert.Equal(ProgressEventKind.Error, e!.Kind);
        Assert.Equal("No .SRT telemetry files found", e.Message);
    }

    [Fact]
    public void Unknown_event_type_is_kept_as_unknown()
    {
        // Forward compatibility: the schema explicitly allows event types we
        // do not recognise; they must flow through, not crash or vanish.
        var e = ProgressEvent.Parse("""{"v": 1, "event": "telemetry", "foo": 1}""");
        Assert.Equal(ProgressEventKind.Unknown, e!.Kind);
        Assert.Equal("telemetry", e.RawEventName);
    }

    [Fact]
    public void Unsupported_contract_version_downgrades_to_unknown()
    {
        // A bumped "v" means the field semantics may have changed under us:
        // keep the line visible but do not interpret it.
        var e = ProgressEvent.Parse("""{"v": 2, "event": "result", "ok": true}""");
        Assert.Equal(ProgressEventKind.Unknown, e!.Kind);
    }

    [Theory]
    [InlineData("not json at all")]
    [InlineData("{\"v\": 1}")]
    [InlineData("[1, 2]")]
    [InlineData("")]
    public void Malformed_lines_parse_to_null(string line)
    {
        Assert.Null(ProgressEvent.Parse(line));
    }
}
