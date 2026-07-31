using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

public class FlightMapOptionsViewModelTests
{
    [Fact]
    public void Defaults_match_the_flightmap_options_defaults()
    {
        var vm = new FlightMapOptionsViewModel();
        Assert.Equal(FlightMapOptions.Defaults, vm.ToOptions());
    }

    [Fact]
    public void Default_selections_are_standard_and_keep()
    {
        var vm = new FlightMapOptionsViewModel();
        Assert.True(vm.Recursive);
        Assert.False(vm.ThreeD);
        Assert.Equal("osm", vm.SelectedTileStyle.Key);
        Assert.Equal(MapPrivacy.Keep, vm.SelectedPrivacy.Value);
        Assert.False(vm.Airspace);
        Assert.Equal(15, vm.JoinGap);
        Assert.False(vm.LinkOriginals);
        Assert.False(vm.ExportAll);
        Assert.Equal("auto", vm.TzOffset);
        Assert.Equal("", vm.Title);
        Assert.Equal("", vm.Output);
    }

    [Fact]
    public void Offers_the_four_tile_styles_and_two_privacy_choices()
    {
        var vm = new FlightMapOptionsViewModel();
        Assert.Equal(["osm", "osm-hot", "opentopomap", "cyclosm"],
            vm.TileStyles.Select(t => t.Key));
        Assert.Equal([MapPrivacy.Keep, MapPrivacy.Fuzz],
            vm.PrivacyOptions.Select(p => p.Value));
    }

    [Fact]
    public void ToOptions_reflects_every_mutated_control()
    {
        var vm = new FlightMapOptionsViewModel
        {
            Recursive = false,
            ThreeD = true,
            Airspace = true,
            JoinGap = 0,
            LinkOriginals = true,
            ExportAll = true,
            TzOffset = "-8",
            Title = "Trip",
            Output = "/out/map.html",
        };
        vm.SelectedTileStyle = vm.TileStyles.Single(t => t.Key == "cyclosm");
        vm.SelectedPrivacy = vm.PrivacyOptions.Single(p => p.Value == MapPrivacy.Fuzz);

        Assert.Equal(
            new FlightMapOptions(false, true, "cyclosm", MapPrivacy.Fuzz, true,
                0, true, true, "-8", "Trip", "/out/map.html"),
            vm.ToOptions());
    }

    // #392: the crossfade caveat mirrors the photo map's ShowsFuzzCaveat, but
    // sharper — under fuzz the 3D map withholds the blend entirely, so the
    // note must appear exactly when the emitted argv pairs --link-originals
    // with --redact fuzz (i.e. only while the 3D toggle keeps the flag live).
    [Fact]
    public void Fuzz_caveat_needs_three_d_and_linking_and_fuzz()
    {
        var vm = new FlightMapOptionsViewModel();
        Assert.False(vm.ShowsFuzzCaveat);      // defaults: nothing on

        vm.ThreeD = true;
        vm.LinkOriginals = true;
        Assert.False(vm.ShowsFuzzCaveat);      // 3D + linked, Keep

        vm.SelectedPrivacy = vm.PrivacyOptions.Single(
            p => p.Value == MapPrivacy.Fuzz);
        Assert.True(vm.ShowsFuzzCaveat);       // 3D + linked + Fuzz

        vm.ThreeD = false;
        Assert.False(vm.ShowsFuzzCaveat);      // flag suppressed without 3D
    }

    [Fact]
    public void Fuzz_caveat_notifies_on_each_of_its_three_inputs()
    {
        var vm = new FlightMapOptionsViewModel();
        var raised = 0;
        vm.PropertyChanged += (_, e) =>
        {
            if (e.PropertyName == nameof(FlightMapOptionsViewModel.ShowsFuzzCaveat))
            {
                raised++;
            }
        };
        vm.ThreeD = true;
        vm.LinkOriginals = true;
        vm.SelectedPrivacy = vm.PrivacyOptions.Single(
            p => p.Value == MapPrivacy.Fuzz);
        Assert.Equal(3, raised);
    }

    // #427: the airspace overlay is suppressed under fuzz (the CLI rejects
    // the pair), so a note must say so exactly while the checkbox is ticked
    // but the flag stays out of the argv. Under 3D the 3D note already
    // names the suppression, so this one stays quiet there.
    [Fact]
    public void Airspace_fuzz_note_needs_airspace_and_fuzz_on_the_flat_map()
    {
        var vm = new FlightMapOptionsViewModel();
        Assert.False(vm.ShowsAirspaceFuzzNote);   // defaults: nothing on

        vm.Airspace = true;
        Assert.False(vm.ShowsAirspaceFuzzNote);   // airspace + Keep

        vm.SelectedPrivacy = vm.PrivacyOptions.Single(
            p => p.Value == MapPrivacy.Fuzz);
        Assert.True(vm.ShowsAirspaceFuzzNote);    // airspace + Fuzz

        vm.ThreeD = true;
        Assert.False(vm.ShowsAirspaceFuzzNote);   // the 3D note covers it
    }

    [Fact]
    public void Airspace_fuzz_note_notifies_on_each_of_its_three_inputs()
    {
        var vm = new FlightMapOptionsViewModel();
        var raised = 0;
        vm.PropertyChanged += (_, e) =>
        {
            if (e.PropertyName
                == nameof(FlightMapOptionsViewModel.ShowsAirspaceFuzzNote))
            {
                raised++;
            }
        };
        vm.Airspace = true;
        vm.SelectedPrivacy = vm.PrivacyOptions.Single(
            p => p.Value == MapPrivacy.Fuzz);
        vm.ThreeD = true;
        Assert.Equal(3, raised);
    }

    // #431 review: the network note must mirror the argv exactly — visible
    // only while --airspace is actually emitted, so it never claims a fetch
    // for a run that makes none (ticked + 3D, ticked + Fuzz).
    [Fact]
    public void Airspace_network_note_shows_exactly_while_the_flag_is_emitted()
    {
        var vm = new FlightMapOptionsViewModel();
        Assert.False(vm.ShowsAirspaceNote);       // defaults: unticked

        vm.Airspace = true;
        Assert.True(vm.ShowsAirspaceNote);        // ticked, Keep, flat map

        vm.ThreeD = true;
        Assert.False(vm.ShowsAirspaceNote);       // suppressed under 3D

        vm.ThreeD = false;
        vm.SelectedPrivacy = vm.PrivacyOptions.Single(
            p => p.Value == MapPrivacy.Fuzz);
        Assert.False(vm.ShowsAirspaceNote);       // suppressed under Fuzz
    }

    [Fact]
    public void Airspace_network_note_notifies_on_each_of_its_three_inputs()
    {
        var vm = new FlightMapOptionsViewModel();
        var raised = 0;
        vm.PropertyChanged += (_, e) =>
        {
            if (e.PropertyName
                == nameof(FlightMapOptionsViewModel.ShowsAirspaceNote))
            {
                raised++;
            }
        };
        vm.Airspace = true;
        vm.SelectedPrivacy = vm.PrivacyOptions.Single(
            p => p.Value == MapPrivacy.Fuzz);
        vm.ThreeD = true;
        Assert.Equal(3, raised);
    }

    // #431 review: the flight record itself fetches airspace and terrain
    // data, so Export all needs its own disclosure whenever the record will
    // actually be written (ticked, flat map, exact locations).
    [Fact]
    public void Record_network_note_shows_exactly_while_the_record_is_written()
    {
        var vm = new FlightMapOptionsViewModel();
        Assert.False(vm.ShowsRecordNetworkNote);  // defaults: unticked

        vm.ExportAll = true;
        Assert.True(vm.ShowsRecordNetworkNote);   // ticked, Keep, flat map

        vm.ThreeD = true;
        Assert.False(vm.ShowsRecordNetworkNote);  // export suppressed

        vm.ThreeD = false;
        vm.SelectedPrivacy = vm.PrivacyOptions.Single(
            p => p.Value == MapPrivacy.Fuzz);
        Assert.False(vm.ShowsRecordNetworkNote);  // record skipped: no fetch
    }

    [Fact]
    public void Record_network_note_notifies_on_each_of_its_three_inputs()
    {
        var vm = new FlightMapOptionsViewModel();
        var raised = 0;
        vm.PropertyChanged += (_, e) =>
        {
            if (e.PropertyName
                == nameof(FlightMapOptionsViewModel.ShowsRecordNetworkNote))
            {
                raised++;
            }
        };
        vm.ExportAll = true;
        vm.SelectedPrivacy = vm.PrivacyOptions.Single(
            p => p.Value == MapPrivacy.Fuzz);
        vm.ThreeD = true;
        Assert.Equal(3, raised);
    }

    // #427: under --format all the CLI deliberately skips the flight record
    // when fuzz is on (a record built on coarsened coordinates would
    // mislead) — the note pre-empts the "where is my record?" surprise.
    [Fact]
    public void Record_skip_note_needs_export_all_and_fuzz_on_the_flat_map()
    {
        var vm = new FlightMapOptionsViewModel();
        Assert.False(vm.ShowsRecordSkipNote);     // defaults: nothing on

        vm.ExportAll = true;
        Assert.False(vm.ShowsRecordSkipNote);     // export + Keep

        vm.SelectedPrivacy = vm.PrivacyOptions.Single(
            p => p.Value == MapPrivacy.Fuzz);
        Assert.True(vm.ShowsRecordSkipNote);      // export + Fuzz

        vm.ThreeD = true;
        Assert.False(vm.ShowsRecordSkipNote);     // export suppressed under 3D
    }

    [Fact]
    public void Record_skip_note_notifies_on_each_of_its_three_inputs()
    {
        var vm = new FlightMapOptionsViewModel();
        var raised = 0;
        vm.PropertyChanged += (_, e) =>
        {
            if (e.PropertyName
                == nameof(FlightMapOptionsViewModel.ShowsRecordSkipNote))
            {
                raised++;
            }
        };
        vm.ExportAll = true;
        vm.SelectedPrivacy = vm.PrivacyOptions.Single(
            p => p.Value == MapPrivacy.Fuzz);
        vm.ThreeD = true;
        Assert.Equal(3, raised);
    }

    [Fact]
    public void Clear_output_resets_to_the_default()
    {
        var vm = new FlightMapOptionsViewModel { Output = "/out/map.html" };
        vm.ClearOutputCommand.Execute(null);
        Assert.Equal("", vm.Output);
    }
}
