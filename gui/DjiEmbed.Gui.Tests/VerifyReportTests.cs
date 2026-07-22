using System.Linq;
using System.Text.Json;
using DjiEmbed.Gui.Services;
using Xunit;

namespace DjiEmbed.Gui.Tests;

public class VerifyReportTests
{
    private static JsonElement Json(string json) =>
        JsonDocument.Parse(json).RootElement.Clone();

    [Fact]
    public void Check_reports_one_row_per_file_with_flag_glyphs()
    {
        var report = VerifyReport.FromCheck(Json(
            """
            {"checked": 2, "files": {
                "C:\\clips\\DJI_0001.MP4":
                    {"gps": true, "altitude": true, "creation_time": true},
                "C:\\clips\\DJI_0002.MP4":
                    {"gps": false, "altitude": true, "creation_time": true}}}
            """));
        Assert.Equal("Checked 2 files", report.Headline);
        Assert.Equal(2, report.Cards.Count);
        Assert.Equal(VerifyStatus.Ok, report.Cards[0].Status);
        Assert.Equal("DJI_0001.MP4", report.Cards[0].Title);
        Assert.Equal("GPS ✓ · Altitude ✓ · Recording time ✓",
            report.Cards[0].Detail);
        Assert.Equal(VerifyStatus.Attention, report.Cards[1].Status);
        Assert.Equal("GPS ✗ · Altitude ✓ · Recording time ✓",
            report.Cards[1].Detail);
    }

    [Fact]
    public void Check_marks_an_unreadable_file_failed()
    {
        var report = VerifyReport.FromCheck(Json(
            """{"checked": 1, "files": {"gone.mp4": {}}}"""));
        Assert.Equal("Checked 1 file", report.Headline);
        var card = Assert.Single(report.Cards);
        Assert.Equal(VerifyStatus.Failed, card.Status);
        Assert.Equal("Couldn't read this file.", card.Detail);
    }

    [Fact]
    public void Validate_clean_run_headline_has_no_cards()
    {
        var report = VerifyReport.FromValidate(Json(
            """
            {"total_files": 2, "valid_pairs": 2, "issues": [],
             "warnings": [], "file_analyses": []}
            """));
        Assert.Equal("Everything pairs up — 2 of 2", report.Headline);
        Assert.Empty(report.Cards);
    }

    [Fact]
    public void Validate_issues_and_warnings_become_attention_rows()
    {
        var report = VerifyReport.FromValidate(Json(
            """
            {"total_files": 2, "valid_pairs": 1,
             "issues": ["No SRT file found for: DJI_0002.MP4"],
             "warnings": ["DJI_0001: drift 1.4s exceeds threshold"],
             "file_analyses": []}
            """));
        Assert.Equal("1 of 2 pairs check out", report.Headline);
        Assert.Equal(2, report.Cards.Count);
        Assert.All(report.Cards,
            c => Assert.Equal(VerifyStatus.Attention, c.Status));
        Assert.Equal("No SRT file found for: DJI_0002.MP4",
            report.Cards[0].Title);
    }

    [Fact]
    public void Sun_reports_stats_and_translates_the_night_flag()
    {
        var report = VerifyReport.FromSun(Json(
            """
            {"file": "DJI_0001.SRT", "points": 120, "sun_computed": 120,
             "utc_start": "2026-07-01T20:00:00Z",
             "utc_end": "2026-07-01T20:02:00Z",
             "elevation_min": -8.1, "elevation_max": -5.2,
             "azimuth_start": 310.5, "azimuth_end": 312.9,
             "flags": ["night"]}
            """));
        Assert.Equal("Sun position over DJI_0001.SRT", report.Headline);
        Assert.Equal(5, report.Cards.Count);
        Assert.Equal("120 in the clip · 120 with a computed sun position",
            report.Cards[0].Detail);
        Assert.Equal("2026-07-01T20:00:00Z → 2026-07-01T20:02:00Z",
            report.Cards[1].Detail);
        Assert.Equal("-8.1° to -5.2°", report.Cards[2].Detail);
        Assert.Equal("310.5° → 312.9°", report.Cards[3].Detail);
        var flag = report.Cards[4];
        Assert.Equal(VerifyStatus.Attention, flag.Status);
        Assert.Equal(
            "Shot at night — the sun was below the horizon the whole time.",
            flag.Title);
        Assert.Equal("", flag.Detail);
    }

    [Fact]
    public void Sun_not_computable_skips_stats_and_fails_the_flag_row()
    {
        var report = VerifyReport.FromSun(Json(
            """
            {"file": "DJI_0001.SRT", "points": 3, "sun_computed": 0,
             "utc_start": null, "utc_end": null, "elevation_min": null,
             "elevation_max": null, "azimuth_start": null,
             "azimuth_end": null, "flags": ["sun_not_computable"]}
            """));
        Assert.Equal(2, report.Cards.Count);
        Assert.Equal(VerifyStatus.Failed, report.Cards[1].Status);
        Assert.Equal(
            "Couldn't work out the sun's position — the file has no usable timestamps.",
            report.Cards[1].Title);
    }

    [Fact]
    public void Malformed_summaries_parse_to_the_empty_report()
    {
        Assert.Equal(VerifyReport.Empty, VerifyReport.FromCheck(null));
        Assert.Equal(VerifyReport.Empty, VerifyReport.FromValidate(null));
        Assert.Equal(VerifyReport.Empty, VerifyReport.FromSun(null));
        Assert.Equal(VerifyReport.Empty,
            VerifyReport.FromCheck(Json("""["not", "an", "object"]""")));
        Assert.Equal(VerifyReport.Empty,
            VerifyReport.FromCheck(Json("""{"files": 7}""")));
    }
}
