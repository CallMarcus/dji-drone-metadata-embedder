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

    // M3c: PhotoMap(folder, opts) is the option-aware argv builder. Defaults
    // must equal M3a's hardcoded output; every option adds flags, omitting at
    // default so the strip stays clean.
    [Fact]
    public void Photo_map_defaults_match_the_m3a_linked_form()
    {
        string[] expected = ["photomap", "/x", "-r", "--link-originals"];
        Assert.Equal(expected,
            CommandBuilder.PhotoMap("/x", PhotoMapOptions.Defaults));
    }

    [Fact]
    public void Photo_map_build_delegates_to_the_options_overload()
    {
        Assert.Equal(
            CommandBuilder.PhotoMap("/x", PhotoMapOptions.Defaults),
            CommandBuilder.Build(WorkspaceModeKind.PhotoMap, "/x"));
    }

    [Fact]
    public void Photo_map_without_recursive_drops_the_flag()
    {
        var argv = CommandBuilder.PhotoMap("/x",
            PhotoMapOptions.Defaults with { Recursive = false });
        Assert.Equal(["photomap", "/x", "--link-originals"], argv);
    }

    [Fact]
    public void Photo_map_without_link_originals_drops_the_flag()
    {
        var argv = CommandBuilder.PhotoMap("/x",
            PhotoMapOptions.Defaults with { LinkOriginals = false });
        Assert.Equal(["photomap", "/x", "-r"], argv);
    }

    [Theory]
    [InlineData("osm-hot")]
    [InlineData("opentopomap")]
    [InlineData("cyclosm")]
    public void Photo_map_passes_a_non_default_tile_style(string key)
    {
        var argv = CommandBuilder.PhotoMap("/x",
            PhotoMapOptions.Defaults with { TileStyle = key });
        Assert.Equal(["photomap", "/x", "-r", "--tile-style", key,
                      "--link-originals"], argv);
    }

    [Fact]
    public void Photo_map_omits_the_default_tile_style()
    {
        Assert.DoesNotContain("--tile-style",
            CommandBuilder.PhotoMap("/x", PhotoMapOptions.Defaults));
    }

    [Fact]
    public void Photo_map_fuzz_redacts()
    {
        var argv = CommandBuilder.PhotoMap("/x",
            PhotoMapOptions.Defaults with { Privacy = MapPrivacy.Fuzz });
        Assert.Equal(["photomap", "/x", "-r", "--redact", "fuzz",
                      "--link-originals"], argv);
    }

    [Fact]
    public void Photo_map_omits_popup_fields_when_every_detail_is_shown()
    {
        Assert.DoesNotContain("--popup-fields",
            CommandBuilder.PhotoMap("/x", PhotoMapOptions.Defaults));
    }

    [Fact]
    public void Photo_map_encodes_no_popup_details_as_none()
    {
        // parse_popup_fields (photomap_html.py) REJECTS an empty comma list;
        // "none" is the only valid encoding of "show nothing".
        var argv = CommandBuilder.PhotoMap("/x",
            PhotoMapOptions.Defaults with { Popup = PopupFields.None });
        Assert.Equal(["photomap", "/x", "-r", "--link-originals",
                      "--popup-fields", "none"], argv);
    }

    [Fact]
    public void Photo_map_lists_a_popup_subset_in_the_cli_field_order()
    {
        // Ticked out of order; the flag must still read name,camera,credit —
        // the POPUP_FIELDS order the CLI documents.
        var argv = CommandBuilder.PhotoMap("/x", PhotoMapOptions.Defaults with
        {
            Popup = new PopupFields(Name: true, Timestamp: false, Camera: true,
                                    Altitude: false, Credit: true),
        });
        Assert.Equal(["photomap", "/x", "-r", "--link-originals",
                      "--popup-fields", "name,camera,credit"], argv);
    }

    [Fact]
    public void Photo_map_export_all_writes_every_format()
    {
        var argv = CommandBuilder.PhotoMap("/x",
            PhotoMapOptions.Defaults with { ExportAll = true });
        Assert.Equal(["photomap", "/x", "-r", "--link-originals",
                      "--format", "all"], argv);
    }

    [Fact]
    public void Photo_map_passes_a_title_and_output()
    {
        var argv = CommandBuilder.PhotoMap("/x", PhotoMapOptions.Defaults with
        {
            Title = "  Sunday flight  ",
            Output = " /out/map.html ",
        });
        // Trimmed, not quoted: quoting belongs to CommandLine.Format (the
        // strip); argv elements reach the process verbatim.
        Assert.Equal(["photomap", "/x", "-r", "--link-originals",
                      "--title", "Sunday flight",
                      "--output", "/out/map.html"], argv);
    }

    [Fact]
    public void Photo_map_ignores_blank_title_and_output()
    {
        var argv = CommandBuilder.PhotoMap("/x",
            PhotoMapOptions.Defaults with { Title = "   ", Output = "  " });
        Assert.Equal(["photomap", "/x", "-r", "--link-originals"], argv);
    }

    [Fact]
    public void Photo_map_all_options_compose_in_a_stable_order()
    {
        var opts = new PhotoMapOptions(
            Recursive: true, TileStyle: "cyclosm", Privacy: MapPrivacy.Fuzz,
            LinkOriginals: true,
            Popup: new PopupFields(Name: true, Timestamp: false, Camera: true,
                                    Altitude: false, Credit: true),
            ExportAll: true, Title: "T", Output: "/o.html");
        Assert.Equal(
            ["photomap", "/x", "-r", "--tile-style", "cyclosm", "--redact", "fuzz",
             "--link-originals", "--popup-fields", "name,camera,credit",
             "--format", "all", "--title", "T", "--output", "/o.html"],
            CommandBuilder.PhotoMap("/x", opts));
    }

    // M3d: Embed(folder, opts) is the option-aware argv builder. Embed is the
    // only folder-taking mode whose defaults carry NO flags at all, so the
    // defaults test is also the guard that no option leaks in at its default
    // value.

    // Every option switched on; shared by the two CLI-only guards below.
    private static readonly EmbedTelemetryOptions EverythingOn = new(
        Privacy: TelemetryPrivacy.Drop, Container: "mkv", ExtractHome: true,
        UseExifTool: true, AudioSidecar: true, DatAuto: true,
        Output: "/out/copies");

    [Fact]
    public void Embed_defaults_match_the_m3a_bare_form()
    {
        string[] expected = ["embed", "/x"];
        Assert.Equal(expected,
            CommandBuilder.Embed("/x", EmbedTelemetryOptions.Defaults));
    }

    [Fact]
    public void Embed_build_delegates_to_the_options_overload()
    {
        Assert.Equal(
            CommandBuilder.Embed("/x", EmbedTelemetryOptions.Defaults),
            CommandBuilder.Build(WorkspaceModeKind.Embed, "/x"));
    }

    [Theory]
    [InlineData(TelemetryPrivacy.Fuzz, "fuzz")]
    [InlineData(TelemetryPrivacy.Drop, "drop")]
    public void Embed_passes_a_non_default_privacy_stance(
        TelemetryPrivacy privacy, string value)
    {
        var argv = CommandBuilder.Embed("/x",
            EmbedTelemetryOptions.Defaults with { Privacy = privacy });
        Assert.Equal(["embed", "/x", "--redact", value], argv);
    }

    [Fact]
    public void Embed_omits_redact_when_locations_are_kept()
    {
        Assert.DoesNotContain("--redact",
            CommandBuilder.Embed("/x", EmbedTelemetryOptions.Defaults));
    }

    [Fact]
    public void Embed_passes_the_mkv_container_and_omits_the_default_mp4()
    {
        var argv = CommandBuilder.Embed("/x",
            EmbedTelemetryOptions.Defaults with { Container = "mkv" });
        Assert.Equal(["embed", "/x", "--container", "mkv"], argv);
        Assert.DoesNotContain("--container",
            CommandBuilder.Embed("/x", EmbedTelemetryOptions.Defaults));
    }

    [Fact]
    public void Embed_passes_extract_home()
    {
        var argv = CommandBuilder.Embed("/x",
            EmbedTelemetryOptions.Defaults with { ExtractHome = true });
        Assert.Equal(["embed", "/x", "--extract-home"], argv);
    }

    [Fact]
    public void Embed_passes_each_advanced_flag()
    {
        Assert.Equal(["embed", "/x", "--exiftool"], CommandBuilder.Embed("/x",
            EmbedTelemetryOptions.Defaults with { UseExifTool = true }));
        Assert.Equal(["embed", "/x", "--audio-sidecar"], CommandBuilder.Embed("/x",
            EmbedTelemetryOptions.Defaults with { AudioSidecar = true }));
        Assert.Equal(["embed", "/x", "--dat-auto"], CommandBuilder.Embed("/x",
            EmbedTelemetryOptions.Defaults with { DatAuto = true }));
    }

    [Fact]
    public void Embed_passes_a_trimmed_output_directory()
    {
        var argv = CommandBuilder.Embed("/x",
            EmbedTelemetryOptions.Defaults with { Output = "  /out/copies  " });
        // Trimmed, not quoted: quoting belongs to CommandLine.Format (the
        // strip); argv elements reach the process verbatim.
        Assert.Equal(["embed", "/x", "--output", "/out/copies"], argv);
    }

    [Fact]
    public void Embed_ignores_a_blank_output()
    {
        Assert.Equal(["embed", "/x"], CommandBuilder.Embed("/x",
            EmbedTelemetryOptions.Defaults with { Output = "   " }));
    }

    [Fact]
    public void Embed_never_offers_overwrite()
    {
        // --overwrite is CLI-only by design (M3d spec): it rewrites the
        // originals in place and must not be reachable from the GUI.
        Assert.DoesNotContain("--overwrite", CommandBuilder.Embed("/x", EverythingOn));
    }

    [Fact]
    public void Embed_never_offers_a_dat_file_path()
    {
        // --dat PATH is CLI-only by design (M3d spec): pointing at one file
        // does not fit a folder-shaped GUI. Only --dat-auto is surfaced.
        // (collection DoesNotContain is element-wise, so --dat-auto does not trip it)
        Assert.DoesNotContain("--dat", CommandBuilder.Embed("/x", EverythingOn));
    }

    [Fact]
    public void Embed_all_options_compose_in_a_stable_order()
    {
        var opts = EverythingOn with { Privacy = TelemetryPrivacy.Fuzz };
        Assert.Equal(
            ["embed", "/x", "--redact", "fuzz", "--container", "mkv",
             "--extract-home", "--exiftool", "--audio-sidecar", "--dat-auto",
             "--output", "/out/copies"],
            CommandBuilder.Embed("/x", opts));
    }

    [Fact]
    public void Convert_defaults_folder_is_bare_batch_gpx()
        => Assert.Equal(["convert", "gpx", "F", "-b"],
            CommandBuilder.Convert("F", batch: true, ConvertTelemetryOptions.Defaults));

    [Fact]
    public void Convert_defaults_file_is_bare_gpx()
        => Assert.Equal(["convert", "gpx", "clip.SRT"],
            CommandBuilder.Convert("clip.SRT", batch: false,
                ConvertTelemetryOptions.Defaults));

    [Fact]
    public void Convert_full_options_emit_in_fixed_order()
    {
        var opts = ConvertTelemetryOptions.Defaults with
        {
            Format = "kml", Privacy = TelemetryPrivacy.Fuzz, TzOffset = "+02:00",
            Footprints = true, FootprintInterval = 5, Model = "air3",
        };
        Assert.Equal(
            ["convert", "kml", "clip.SRT", "--redact", "fuzz",
             "--tz-offset", "+02:00", "--footprint",
             "--footprint-interval", "5", "--model", "air3"],
            CommandBuilder.Convert("clip.SRT", batch: false, opts));
    }

    [Fact]
    public void Convert_footprint_flags_only_reach_formats_that_take_them()
    {
        // --footprint is meaningless on gpx: Click declares it on the shared
        // convert command, but run_one silently never forwards it there.
        var opts = ConvertTelemetryOptions.Defaults with { Footprints = true };
        Assert.DoesNotContain("--footprint",
            CommandBuilder.Convert("F", batch: true, opts));
    }

    [Fact]
    public void Convert_cot_settings_only_reach_cot()
    {
        var cot = ConvertTelemetryOptions.Defaults with
        { Format = "cot", CotInterval = 2.5, CotType = "a-f-A" };
        Assert.Equal(
            ["convert", "cot", "F", "-b", "--interval", "2.5",
             "--cot-type", "a-f-A"],
            CommandBuilder.Convert("F", batch: true, cot));
        var gpx = cot with { Format = "gpx" };
        Assert.DoesNotContain("--interval",
            CommandBuilder.Convert("F", batch: true, gpx));
    }

    [Fact]
    public void Convert_output_applies_to_single_files_only()
    {
        // The CLI's batch loop has no -o: every output lands beside its source.
        var opts = ConvertTelemetryOptions.Defaults with { Output = "out.gpx" };
        Assert.Equal(["convert", "gpx", "clip.SRT", "--output", "out.gpx"],
            CommandBuilder.Convert("clip.SRT", batch: false, opts));
        Assert.DoesNotContain("--output",
            CommandBuilder.Convert("F", batch: true, opts));
    }

    [Fact]
    public void Convert_auto_and_blank_tz_are_omitted()
    {
        foreach (var tz in new[] { "", "  ", "auto", "AUTO" })
        {
            Assert.DoesNotContain("--tz-offset", CommandBuilder.Convert(
                "F", true, ConvertTelemetryOptions.Defaults with { TzOffset = tz }));
        }
    }

    [Fact]
    public void Convert_drop_privacy_emits_redact_drop()
        => Assert.Equal(["convert", "gpx", "F", "-b", "--redact", "drop"],
            CommandBuilder.Convert("F", batch: true,
                ConvertTelemetryOptions.Defaults with { Privacy = TelemetryPrivacy.Drop }));

    [Fact]
    public void Convert_footprints_at_default_interval_and_empty_model_emit_footprint_alone()
    {
        var opts = ConvertTelemetryOptions.Defaults with
        { Format = "geojson", Footprints = true };
        Assert.Equal(["convert", "geojson", "F", "-b", "--footprint"],
            CommandBuilder.Convert("F", batch: true, opts));
    }

    [Fact]
    public void Convert_cot_at_all_defaults_emits_no_cot_flags()
        => Assert.Equal(["convert", "cot", "F", "-b"],
            CommandBuilder.Convert("F", batch: true,
                ConvertTelemetryOptions.Defaults with { Format = "cot" }));

    [Fact]
    public void Convert_trims_model()
    {
        var opts = ConvertTelemetryOptions.Defaults with
        { Format = "kml", Footprints = true, Model = " air3 " };
        Assert.Equal(["convert", "kml", "F", "-b", "--footprint", "--model", "air3"],
            CommandBuilder.Convert("F", batch: true, opts));
    }

    [Fact]
    public void Convert_cot_type_trimmed_to_the_default_is_omitted()
        => Assert.Equal(["convert", "cot", "F", "-b"],
            CommandBuilder.Convert("F", batch: true, ConvertTelemetryOptions.Defaults with
            { Format = "cot", CotType = " a-n-A " }));

    [Fact]
    public void Convert_blank_output_on_a_single_file_is_omitted()
        => Assert.Equal(["convert", "gpx", "clip.SRT"],
            CommandBuilder.Convert("clip.SRT", batch: false,
                ConvertTelemetryOptions.Defaults with { Output = "  " }));

    [Fact]
    public void Build_convert_arm_uses_defaults_batch()
        => Assert.Equal(["convert", "gpx", "F", "-b"],
            CommandBuilder.Build(WorkspaceModeKind.Convert, "F"));

    [Fact]
    public void Verify_defaults_run_bare_check() =>
        Assert.Equal(["check", "/f"],
            CommandBuilder.Verify("/f", VerifyTelemetryOptions.Defaults));

    [Fact]
    public void Verify_validate_omits_the_default_drift_threshold()
    {
        var opts = VerifyTelemetryOptions.Defaults with
        { SubAction = VerifySubAction.Validate };
        Assert.Equal(["validate", "/f"], CommandBuilder.Verify("/f", opts));
    }

    [Fact]
    public void Verify_validate_emits_drift_threshold_invariantly()
    {
        var opts = VerifyTelemetryOptions.Defaults with
        { SubAction = VerifySubAction.Validate, DriftThreshold = 2.5 };
        Assert.Equal(["validate", "/f", "--drift-threshold", "2.5"],
            CommandBuilder.Verify("/f", opts));
    }

    [Fact]
    public void Verify_sun_emits_tz_offset_when_set()
    {
        var opts = VerifyTelemetryOptions.Defaults with
        { SubAction = VerifySubAction.Sun, TzOffset = "+02:00" };
        Assert.Equal(["verify-sun", "/clip.SRT", "--tz-offset", "+02:00"],
            CommandBuilder.Verify("/clip.SRT", opts));
    }

    [Fact]
    public void Verify_sun_treats_empty_and_auto_tz_as_default()
    {
        var sun = VerifyTelemetryOptions.Defaults with
        { SubAction = VerifySubAction.Sun };
        Assert.Equal(["verify-sun", "/c.SRT"],
            CommandBuilder.Verify("/c.SRT", sun));
        Assert.Equal(["verify-sun", "/c.SRT"],
            CommandBuilder.Verify("/c.SRT", sun with { TzOffset = " auto " }));
    }
}
