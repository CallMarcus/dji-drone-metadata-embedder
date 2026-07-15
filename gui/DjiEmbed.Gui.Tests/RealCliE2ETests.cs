using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

// Opt-in end-to-end check against the real Python CLI. CI's gui job has no
// Python environment, so this only runs when DJIEMBED_E2E_CLI points at a
// dji-embed executable (or wrapper script) — used before releases and when
// touching the runner.
public class RealCliE2ETests
{
    private const string EnvVar = "DJIEMBED_E2E_CLI";

    private const string Srt =
        "1\n00:00:00,000 --> 00:00:01,000\n"
        + "<font size=\"28\">FrameCnt: 1, DiffTime: 1000ms\n"
        + "2026-06-15 12:00:00.000\n"
        + "[latitude: 34.0] [longitude: -84.0] "
        + "[rel_alt: 1.000 abs_alt: 100.0]</font>\n";

    [Fact]
    public async Task Doctor_run_through_the_real_cli_yields_a_tools_summary()
    {
        var cli = Environment.GetEnvironmentVariable(EnvVar);
        Assert.SkipWhen(string.IsNullOrEmpty(cli),
            $"set {EnvVar} to a dji-embed executable to run this test");

        var result = await new DjiEmbedRunner().RunAsync(
            cli!, ["doctor"], ct: TestContext.Current.CancellationToken);

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
        var cli = Environment.GetEnvironmentVariable(EnvVar);
        Assert.SkipWhen(string.IsNullOrEmpty(cli),
            $"set {EnvVar} to a dji-embed executable to run this test");

        var dir = Directory.CreateTempSubdirectory("djiembed-e2e").FullName;
        try
        {
            File.WriteAllText(Path.Combine(dir, "DJI_0001.SRT"), Srt);
            var seen = new List<ProgressEvent>();
            var result = await new DjiEmbedRunner().RunAsync(
                cli!, ["flightmap", dir],
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
}
