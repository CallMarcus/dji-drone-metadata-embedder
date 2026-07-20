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
        Assert.Equal("osm", vm.SelectedTileStyle.Key);
        Assert.Equal(MapPrivacy.Keep, vm.SelectedPrivacy.Value);
        Assert.Equal(15, vm.JoinGap);
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
            JoinGap = 0,
            ExportAll = true,
            TzOffset = "-8",
            Title = "Trip",
            Output = "/out/map.html",
        };
        vm.SelectedTileStyle = vm.TileStyles.Single(t => t.Key == "cyclosm");
        vm.SelectedPrivacy = vm.PrivacyOptions.Single(p => p.Value == MapPrivacy.Fuzz);

        Assert.Equal(
            new FlightMapOptions(false, "cyclosm", MapPrivacy.Fuzz, 0, true,
                "-8", "Trip", "/out/map.html"),
            vm.ToOptions());
    }

    [Fact]
    public void Clear_output_resets_to_the_default()
    {
        var vm = new FlightMapOptionsViewModel { Output = "/out/map.html" };
        vm.ClearOutputCommand.Execute(null);
        Assert.Equal("", vm.Output);
    }
}
