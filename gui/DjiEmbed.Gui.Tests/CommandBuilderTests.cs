using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

// M3a: one source of truth for each mode's argv (no --progress; the runner
// appends that). These goldens pin today's behaviour so later option slices
// can only extend it deliberately.
public class CommandBuilderTests
{
    [Fact]
    public void Flight_map_builds_recursive_flightmap()
    {
        string[] expected = ["flightmap", "/x", "-r"];
        Assert.Equal(expected, CommandBuilder.Build(WorkspaceModeKind.FlightMap, "/x"));
    }

    [Fact]
    public void Photo_map_links_originals_for_the_pano_viewer()
    {
        string[] expected = ["photomap", "/x", "-r", "--link-originals"];
        Assert.Equal(expected, CommandBuilder.Build(WorkspaceModeKind.PhotoMap, "/x"));
    }

    [Fact]
    public void Embed_is_bare()
    {
        string[] expected = ["embed", "/x"];
        Assert.Equal(expected, CommandBuilder.Build(WorkspaceModeKind.Embed, "/x"));
    }

    [Fact]
    public void Setup_is_doctor_and_ignores_the_folder()
    {
        string[] expected = ["doctor"];
        Assert.Equal(expected, CommandBuilder.Build(WorkspaceModeKind.Setup, null));
    }

    [Fact]
    public void No_mode_ever_includes_the_progress_flag()
    {
        foreach (var kind in Enum.GetValues<WorkspaceModeKind>())
        {
            Assert.DoesNotContain("--progress", CommandBuilder.Build(kind, "/x"));
        }
    }

    // M3b: FlightMap(folder, opts) is the option-aware argv builder. Defaults
    // must equal M3a's hardcoded output; every option adds flags, omitting at
    // default so the strip stays clean.
    [Fact]
    public void Flight_map_defaults_match_the_m3a_recursive_form()
    {
        string[] expected = ["flightmap", "/x", "-r"];
        Assert.Equal(expected,
            CommandBuilder.FlightMap("/x", FlightMapOptions.Defaults));
    }

    [Fact]
    public void Flight_map_build_delegates_to_the_options_overload()
    {
        Assert.Equal(
            CommandBuilder.FlightMap("/x", FlightMapOptions.Defaults),
            CommandBuilder.Build(WorkspaceModeKind.FlightMap, "/x"));
    }

    [Fact]
    public void Recursive_off_drops_the_r_flag()
    {
        var opts = FlightMapOptions.Defaults with { Recursive = false };
        Assert.Equal(["flightmap", "/x"], CommandBuilder.FlightMap("/x", opts));
    }

    [Theory]
    [InlineData("osm-hot")]
    [InlineData("opentopomap")]
    [InlineData("cyclosm")]
    public void Non_default_tile_style_is_emitted(string key)
    {
        var opts = FlightMapOptions.Defaults with { TileStyle = key };
        Assert.Equal(["flightmap", "/x", "-r", "--tile-style", key],
            CommandBuilder.FlightMap("/x", opts));
    }

    [Fact]
    public void Default_tile_style_is_omitted()
    {
        var opts = FlightMapOptions.Defaults with { TileStyle = "osm" };
        Assert.DoesNotContain("--tile-style", CommandBuilder.FlightMap("/x", opts));
    }

    [Fact]
    public void Fuzz_privacy_adds_redact_fuzz()
    {
        var opts = FlightMapOptions.Defaults with { Privacy = MapPrivacy.Fuzz };
        Assert.Equal(["flightmap", "/x", "-r", "--redact", "fuzz"],
            CommandBuilder.FlightMap("/x", opts));
    }

    [Fact]
    public void Keep_privacy_omits_redact()
    {
        Assert.DoesNotContain("--redact",
            CommandBuilder.FlightMap("/x", FlightMapOptions.Defaults));
    }

    [Theory]
    [InlineData(0)]
    [InlineData(30)]
    public void Non_default_join_gap_is_emitted(int seconds)
    {
        var opts = FlightMapOptions.Defaults with { JoinGap = seconds };
        Assert.Equal(
            ["flightmap", "/x", "-r", "--join-gap", seconds.ToString()],
            CommandBuilder.FlightMap("/x", opts));
    }

    [Fact]
    public void Default_join_gap_of_15_is_omitted()
    {
        Assert.DoesNotContain("--join-gap",
            CommandBuilder.FlightMap("/x", FlightMapOptions.Defaults));
    }

    [Fact]
    public void Export_all_adds_format_all()
    {
        var opts = FlightMapOptions.Defaults with { ExportAll = true };
        Assert.Equal(["flightmap", "/x", "-r", "--format", "all"],
            CommandBuilder.FlightMap("/x", opts));
    }

    [Theory]
    [InlineData("auto")]
    [InlineData("AUTO")]
    [InlineData("")]
    [InlineData("  ")]
    public void Auto_or_blank_timezone_is_omitted(string tz)
    {
        var opts = FlightMapOptions.Defaults with { TzOffset = tz };
        Assert.DoesNotContain("--tz-offset", CommandBuilder.FlightMap("/x", opts));
    }

    [Fact]
    public void Explicit_timezone_is_emitted_trimmed()
    {
        var opts = FlightMapOptions.Defaults with { TzOffset = " +05:30 " };
        Assert.Equal(["flightmap", "/x", "-r", "--tz-offset", "+05:30"],
            CommandBuilder.FlightMap("/x", opts));
    }

    [Fact]
    public void Title_is_emitted_when_set_and_stays_one_argument()
    {
        var opts = FlightMapOptions.Defaults with { Title = "Summer trip" };
        Assert.Equal(["flightmap", "/x", "-r", "--title", "Summer trip"],
            CommandBuilder.FlightMap("/x", opts));
    }

    [Fact]
    public void Blank_title_is_omitted()
    {
        var opts = FlightMapOptions.Defaults with { Title = "   " };
        Assert.DoesNotContain("--title", CommandBuilder.FlightMap("/x", opts));
    }

    [Fact]
    public void Output_override_is_emitted()
    {
        var opts = FlightMapOptions.Defaults with { Output = "/out/map.html" };
        Assert.Equal(["flightmap", "/x", "-r", "--output", "/out/map.html"],
            CommandBuilder.FlightMap("/x", opts));
    }

    [Fact]
    public void All_options_compose_in_a_stable_order()
    {
        var opts = new FlightMapOptions(
            Recursive: false, TileStyle: "cyclosm", Privacy: MapPrivacy.Fuzz,
            JoinGap: 0, ExportAll: true, TzOffset: "-8", Title: "T", Output: "/o.html");
        Assert.Equal(
            ["flightmap", "/x", "--tile-style", "cyclosm", "--redact", "fuzz",
             "--join-gap", "0", "--format", "all", "--tz-offset", "-8",
             "--title", "T", "--output", "/o.html"],
            CommandBuilder.FlightMap("/x", opts));
    }
}
