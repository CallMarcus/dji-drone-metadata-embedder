using System.Globalization;
using System.Text;
using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

// Opt-in end-to-end checks against the real Python CLI. CI's gui job has no
// Python environment, so these only run when DJIEMBED_E2E_CLI points at a
// dji-embed executable (or wrapper script) — used before releases and when
// touching the runner. The option-carrying tests build their argv through
// CommandBuilder, so they pin what the OPTIONS panels produce against the
// real CLI and the files it actually writes.
public class RealCliE2ETests
{
    private const string EnvVar = "DJIEMBED_E2E_CLI";

    private const string Srt =
        "1\n00:00:00,000 --> 00:00:01,000\n"
        + "<font size=\"28\">FrameCnt: 1, DiffTime: 1000ms\n"
        + "2026-06-15 12:00:00.000\n"
        + "[latitude: 34.0] [longitude: -84.0] "
        + "[rel_alt: 1.000 abs_alt: 100.0]</font>\n";

    private static string RequireCli()
    {
        var cli = Environment.GetEnvironmentVariable(EnvVar);
        Assert.SkipWhen(string.IsNullOrEmpty(cli),
            $"set {EnvVar} to a dji-embed executable to run this test");
        return cli!;
    }

    /// <summary>
    /// A one-second-per-fix SRT track: <paramref name="points"/> fixes from
    /// 12:00:<paramref name="startSecond"/>, drifting north ~1 m per fix from
    /// <paramref name="startLat"/>. Coordinates carry six decimals so fuzz
    /// redaction (three decimals) is observable in the output files.
    /// </summary>
    private static string SrtTrack(int startSecond, double startLat, int points)
    {
        var sb = new StringBuilder();
        for (var i = 0; i < points; i++)
        {
            var lat = startLat + i * 0.000010;
            sb.Append(CultureInfo.InvariantCulture,
                $"{i + 1}\n00:00:{i:00},000 --> 00:00:{i + 1:00},000\n");
            sb.Append(CultureInfo.InvariantCulture,
                $"<font size=\"28\">FrameCnt: {i + 1}, DiffTime: 1000ms\n");
            sb.Append(CultureInfo.InvariantCulture,
                $"2026-06-15 12:00:{startSecond + i:00}.000\n");
            sb.Append(CultureInfo.InvariantCulture,
                $"[latitude: {lat:F6}] [longitude: -84.654321] ");
            sb.Append("[rel_alt: 10.000 abs_alt: 110.0]</font>\n\n");
        }
        return sb.ToString();
    }

    /// <summary>
    /// One flight recorded as two files, the way DJI splits at the 4 GB
    /// limit: the second starts 2 s after the first ends, ~5 m further along
    /// the same line — inside the default 15 s join window.
    /// </summary>
    private static void WriteSplitRecording(string dir)
    {
        File.WriteAllText(
            Path.Combine(dir, "DJI_0001.SRT"), SrtTrack(0, 34.123456, 5));
        File.WriteAllText(
            Path.Combine(dir, "DJI_0002.SRT"), SrtTrack(6, 34.123506, 5));
    }

    // An 8×8 JPEG carrying synthetic EXIF: Model FC-E2E-CAM, Artist
    // "E2E Credit", DateTimeOriginal 2026-06-15 12:00:00 and a fictitious
    // GPS fix (34.0567 N, 84.1234 W, 123.4 m) — one exercise photo for every
    // popup field. Generated with Pillow + ExifTool; no real location.
    private const string GpsTaggedJpegBase64 =
        "/9j/4AAQSkZJRgABAQAAAQABAAD/4QGGRXhpZgAATU0AKgAAAAgACAEQAAIAAAALAAAAbgEaAAUA"
        + "AAABAAAAegEbAAUAAAABAAAAggEoAAMAAAABAAEAAAE7AAIAAAALAAAAigITAAMAAAABAAEAAIdp"
        + "AAQAAAABAAAAloglAAQAAAABAAAA7AAAAABGQy1FMkUtQ0FNAAAAAAABAAAAAQAAAAEAAAABRTJF"
        + "IENyZWRpdAAAAAWQAAAHAAAABDAyMzKQAwACAAAAFAAAANiRAQAHAAAABAECAwCgAAAHAAAABDAx"
        + "MDCgAQADAAAAAf//AAAAAAAAMjAyNjowNjoxNSAxMjowMDowMAAABwAAAAEAAAAEAgMAAAABAAIA"
        + "AAACTgAAAAACAAUAAAADAAABRgADAAIAAAACVwAAAAAEAAUAAAADAAABXgAFAAEAAAABAAAAAAAG"
        + "AAUAAAABAAABdgAAAAAAAAAiAAAAAQAAAAMAAAABAAACWwAAABkAAABUAAAAAQAAAAcAAAABAAAC"
        + "XgAAABkAAAJpAAAABf/bAEMAEAsMDgwKEA4NDhIREBMYKBoYFhYYMSMlHSg6Mz08OTM4N0BIXE5A"
        + "RFdFNzhQbVFXX2JnaGc+TXF5cGR4XGVnY//bAEMBERISGBUYLxoaL2NCOEJjY2NjY2NjY2NjY2Nj"
        + "Y2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY//AABEIAAgACAMBIgACEQEDEQH/"
        + "xAAfAAABBQEBAQEBAQAAAAAAAAAAAQIDBAUGBwgJCgv/xAC1EAACAQMDAgQDBQUEBAAAAX0BAgMA"
        + "BBEFEiExQQYTUWEHInEUMoGRoQgjQrHBFVLR8CQzYnKCCQoWFxgZGiUmJygpKjQ1Njc4OTpDREVG"
        + "R0hJSlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0"
        + "tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4eLj5OXm5+jp6vHy8/T19vf4+fr/xAAfAQADAQEBAQEB"
        + "AQEBAAAAAAAAAQIDBAUGBwgJCgv/xAC1EQACAQIEBAMEBwUEBAABAncAAQIDEQQFITEGEkFRB2Fx"
        + "EyIygQgUQpGhscEJIzNS8BVictEKFiQ04SXxFxgZGiYnKCkqNTY3ODk6Q0RFRkdISUpTVFVWV1hZ"
        + "WmNkZWZnaGlqc3R1dnd4eXqCg4SFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TF"
        + "xsfIycrS09TV1tfY2dri4+Tl5ufo6ery8/T19vf4+fr/2gAMAwEAAhEDEQA/APQKKKKAP//Z";

    [Fact]
    public async Task Doctor_run_through_the_real_cli_yields_a_tools_summary()
    {
        var cli = RequireCli();

        var result = await new DjiEmbedRunner().RunAsync(
            cli, ["doctor"], ct: TestContext.Current.CancellationToken);

        Assert.Equal(0, result.ExitCode);
        Assert.Empty(result.MalformedLines);
        Assert.NotNull(result.Terminal);
        Assert.Equal(ProgressEventKind.Result, result.Terminal!.Kind);
        Assert.True(result.Terminal.Summary!.Value
            .GetProperty("tools").GetProperty("exiftool")
            .TryGetProperty("present", out _));
    }

    [Fact]
    public async Task Flightmap_run_through_the_real_cli_succeeds()
    {
        var cli = RequireCli();

        var dir = Directory.CreateTempSubdirectory("djiembed-e2e").FullName;
        try
        {
            File.WriteAllText(Path.Combine(dir, "DJI_0001.SRT"), Srt);
            var seen = new List<ProgressEvent>();
            var result = await new DjiEmbedRunner().RunAsync(
                cli, ["flightmap", dir],
                new Progress<ProgressEvent>(seen.Add),
                TestContext.Current.CancellationToken);

            Assert.True(result.Success,
                $"exit={result.ExitCode} stderr={result.StderrText}");
            Assert.Empty(result.MalformedLines);
            var output = Assert.Single(result.Terminal!.Outputs!);
            Assert.True(File.Exists(output), $"missing output {output}");
        }
        finally
        {
            Directory.Delete(dir, recursive: true);
        }
    }

    [Fact]
    public async Task Flightmap_gui_options_shape_all_three_export_formats()
    {
        var cli = RequireCli();

        var dir = Directory.CreateTempSubdirectory("djiembed-e2e").FullName;
        try
        {
            WriteSplitRecording(dir);
            var opts = FlightMapOptions.Defaults with
            {
                TileStyle = "opentopomap",
                Privacy = MapPrivacy.Fuzz,
                ExportAll = true,
                Title = "E2E Custom Title",
            };
            var result = await new DjiEmbedRunner().RunAsync(
                cli, CommandBuilder.FlightMap(dir, opts),
                ct: TestContext.Current.CancellationToken);

            Assert.True(result.Success,
                $"exit={result.ExitCode} stderr={result.StderrText}");
            var outputs = result.Terminal!.Outputs!;
            Assert.Equal(
                [".html", ".kml", ".geojson"],
                outputs.Select(Path.GetExtension));
            Assert.All(outputs,
                o => Assert.True(File.Exists(o), $"missing output {o}"));

            var html = File.ReadAllText(outputs[0]);
            Assert.Contains("E2E Custom Title", html);
            Assert.Contains("opentopomap", html);
            // Fuzz coarsens to three decimals: the coarse latitude is what
            // the map plots, and the six-decimal fix survives in no format.
            Assert.Contains("34.123,", html);
            foreach (var o in outputs)
            {
                Assert.DoesNotContain("34.123456", File.ReadAllText(o));
            }
        }
        finally
        {
            Directory.Delete(dir, recursive: true);
        }
    }

    [Fact]
    public async Task Flightmap_join_gap_zero_splits_what_the_default_joins()
    {
        var cli = RequireCli();

        var dir = Directory.CreateTempSubdirectory("djiembed-e2e").FullName;
        try
        {
            WriteSplitRecording(dir);
            var runner = new DjiEmbedRunner();

            var joined = await runner.RunAsync(
                cli,
                CommandBuilder.FlightMap(dir, FlightMapOptions.Defaults with
                {
                    Output = Path.Combine(dir, "joined.html"),
                }),
                ct: TestContext.Current.CancellationToken);
            Assert.True(joined.Success,
                $"exit={joined.ExitCode} stderr={joined.StderrText}");
            var joinedSummary = joined.Terminal!.Summary!.Value;
            Assert.Equal(1, joinedSummary.GetProperty("flights").GetInt32());
            Assert.Equal(
                2, joinedSummary.GetProperty("joined_files").GetInt32());

            var split = await runner.RunAsync(
                cli,
                CommandBuilder.FlightMap(dir, FlightMapOptions.Defaults with
                {
                    JoinGap = 0,
                    Output = Path.Combine(dir, "split.html"),
                }),
                ct: TestContext.Current.CancellationToken);
            Assert.True(split.Success,
                $"exit={split.ExitCode} stderr={split.StderrText}");
            var splitSummary = split.Terminal!.Summary!.Value;
            Assert.Equal(2, splitSummary.GetProperty("flights").GetInt32());
            Assert.Equal(
                0, splitSummary.GetProperty("joined_files").GetInt32());
        }
        finally
        {
            Directory.Delete(dir, recursive: true);
        }
    }

    [Fact]
    public async Task Photomap_unticked_popup_fields_are_stripped_from_the_html_itself()
    {
        var cli = RequireCli();

        var dir = Directory.CreateTempSubdirectory("djiembed-e2e").FullName;
        try
        {
            File.WriteAllBytes(
                Path.Combine(dir, "DJI_0042.JPG"),
                Convert.FromBase64String(GpsTaggedJpegBase64));
            var runner = new DjiEmbedRunner();

            var full = await runner.RunAsync(
                cli,
                CommandBuilder.PhotoMap(dir, PhotoMapOptions.Defaults with
                {
                    Output = Path.Combine(dir, "full.html"),
                }),
                ct: TestContext.Current.CancellationToken);
            // photomap is the one map command with a tool dependency; the
            // flightmap E2E coverage should not hinge on ExifTool being
            // installed wherever DJIEMBED_E2E_CLI is set.
            Assert.SkipWhen(
                !full.Success && full.StderrText.Contains("ExifTool not found"),
                "photomap needs ExifTool on PATH to run this test");
            Assert.True(full.Success,
                $"exit={full.ExitCode} stderr={full.StderrText}");
            var fullHtml =
                File.ReadAllText(Assert.Single(full.Terminal!.Outputs!));
            // Positive control: with every field ticked, the fixture's
            // camera, timestamp and credit all reach the map.
            Assert.Contains("FC-E2E-CAM", fullHtml);
            Assert.Contains("2026-06-15 12:00:00", fullHtml);
            Assert.Contains("E2E Credit", fullHtml);

            var trimmed = await runner.RunAsync(
                cli,
                CommandBuilder.PhotoMap(dir, PhotoMapOptions.Defaults with
                {
                    Popup = new PopupFields(
                        Name: true, Timestamp: false, Camera: false,
                        Altitude: true, Credit: false),
                    Output = Path.Combine(dir, "trimmed.html"),
                }),
                ct: TestContext.Current.CancellationToken);
            Assert.True(trimmed.Success,
                $"exit={trimmed.ExitCode} stderr={trimmed.StderrText}");
            var trimmedHtml =
                File.ReadAllText(Assert.Single(trimmed.Terminal!.Outputs!));
            // Unticked fields must be absent from the file itself, not merely
            // hidden by popup JS — a shared map must not leak in its source
            // what it hides in its UI (issue #296).
            Assert.Contains("DJI_0042", trimmedHtml);
            Assert.DoesNotContain("FC-E2E-CAM", trimmedHtml);
            Assert.DoesNotContain("2026-06-15", trimmedHtml);
            Assert.DoesNotContain("E2E Credit", trimmedHtml);
        }
        finally
        {
            Directory.Delete(dir, recursive: true);
        }
    }
}
