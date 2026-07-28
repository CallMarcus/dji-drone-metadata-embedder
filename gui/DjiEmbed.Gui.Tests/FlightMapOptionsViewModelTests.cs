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
            new FlightMapOptions(false, true, "cyclosm", MapPrivacy.Fuzz, 0,
                true, true, "-8", "Trip", "/out/map.html"),
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

    [Fact]
    public void Clear_output_resets_to_the_default()
    {
        var vm = new FlightMapOptionsViewModel { Output = "/out/map.html" };
        vm.ClearOutputCommand.Execute(null);
        Assert.Equal("", vm.Output);
    }
}
