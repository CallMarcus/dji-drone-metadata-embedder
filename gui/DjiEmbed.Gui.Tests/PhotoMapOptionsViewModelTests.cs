using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

public class PhotoMapOptionsViewModelTests
{
    [Fact]
    public void Defaults_match_the_photomap_options_defaults()
    {
        var vm = new PhotoMapOptionsViewModel();
        Assert.Equal(PhotoMapOptions.Defaults, vm.ToOptions());
    }

    [Fact]
    public void Default_selections_are_standard_keep_and_linked()
    {
        var vm = new PhotoMapOptionsViewModel();
        Assert.True(vm.Recursive);
        Assert.Equal("osm", vm.SelectedTileStyle.Key);
        Assert.Equal(MapPrivacy.Keep, vm.SelectedPrivacy.Value);
        Assert.True(vm.LinkOriginals);
        Assert.False(vm.ExportAll);
        Assert.Equal("", vm.Title);
        Assert.Equal("", vm.Output);
    }

    [Fact]
    public void Every_popup_detail_starts_ticked()
    {
        var vm = new PhotoMapOptionsViewModel();
        Assert.True(vm.ShowName);
        Assert.True(vm.ShowTimestamp);
        Assert.True(vm.ShowCamera);
        Assert.True(vm.ShowAltitude);
        Assert.True(vm.ShowCredit);
        Assert.Equal(PopupFields.All, vm.ToOptions().Popup);
    }

    [Fact]
    public void Shares_the_tile_list_with_the_flight_map_panel()
    {
        Assert.Same(TileChoice.All, new PhotoMapOptionsViewModel().TileStyles);
    }

    [Fact]
    public void ToOptions_reflects_every_mutated_control()
    {
        var vm = new PhotoMapOptionsViewModel
        {
            Recursive = false,
            LinkOriginals = false,
            ShowCamera = false,
            ShowAltitude = false,
            ExportAll = true,
            Title = "Sunday flight",
            Output = "/out/map.html",
        };
        vm.SelectedTileStyle = vm.TileStyles.Single(t => t.Key == "opentopomap");
        vm.SelectedPrivacy =
            vm.PrivacyOptions.Single(p => p.Value == MapPrivacy.Fuzz);

        var opts = vm.ToOptions();
        Assert.Equal(new PhotoMapOptions(
            Recursive: false,
            TileStyle: "opentopomap",
            Privacy: MapPrivacy.Fuzz,
            LinkOriginals: false,
            Popup: new PopupFields(Name: true, Timestamp: true, Camera: false,
                                   Altitude: false, Credit: true),
            ExportAll: true,
            Title: "Sunday flight",
            Output: "/out/map.html"), opts);
    }

    // The CLI prints this caveat on stderr, where the GUI would bury it in the
    // warnings area — so the panel says it at the moment of the choice.
    [Fact]
    public void Fuzz_caveat_shows_only_when_fuzzing_and_linking()
    {
        var vm = new PhotoMapOptionsViewModel();
        Assert.False(vm.ShowsFuzzCaveat);      // Keep + linked

        vm.SelectedPrivacy =
            vm.PrivacyOptions.Single(p => p.Value == MapPrivacy.Fuzz);
        Assert.True(vm.ShowsFuzzCaveat);       // Fuzz + linked

        vm.LinkOriginals = false;
        Assert.False(vm.ShowsFuzzCaveat);      // Fuzz, nothing linked
    }

    [Fact]
    public void Fuzz_caveat_notifies_on_both_of_its_inputs()
    {
        var vm = new PhotoMapOptionsViewModel();
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);

        vm.SelectedPrivacy =
            vm.PrivacyOptions.Single(p => p.Value == MapPrivacy.Fuzz);
        vm.LinkOriginals = false;

        Assert.Equal(2, notified.Count(
            n => n == nameof(PhotoMapOptionsViewModel.ShowsFuzzCaveat)));
    }

    [Fact]
    public void Clear_output_resets_to_the_source_folder()
    {
        var vm = new PhotoMapOptionsViewModel { Output = "/out/map.html" };
        vm.ClearOutputCommand.Execute(null);
        Assert.Equal("", vm.Output);
    }
}
