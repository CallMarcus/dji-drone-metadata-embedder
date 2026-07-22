using Avalonia.Controls;
using Avalonia.Headless.XUnit;
using DjiEmbed.Gui.Services;
using DjiEmbed.Gui.ViewModels;
using DjiEmbed.Gui.Views;

namespace DjiEmbed.Gui.Tests;

// M5a window-bounds persistence. The restore *decision* (screen
// intersection) is pure and covered in GuiStateTests; these tests cover
// the window plumbing on the headless platform, where no screens are
// reported and RestorableOn therefore always allows the restore.
public class MainWindowStateTests
{
    private static GuiStateStore StoreWith(WindowBounds bounds)
    {
        var store = GuiStateStore.Ephemeral();
        store.SaveWindow(bounds);
        return store;
    }

    [AvaloniaFact]
    public void Restores_saved_size_on_startup()
    {
        var window = new MainWindow(
            StoreWith(new WindowBounds(50, 60, 1200, 800, Maximized: false)))
        { DataContext = new MainViewModel() };
        window.Show();

        Assert.Equal(1200, window.Width);
        Assert.Equal(800, window.Height);
        Assert.Equal(WindowStartupLocation.Manual,
            window.WindowStartupLocation);
        window.Close();
    }

    [AvaloniaFact]
    public void Restores_maximized_with_normal_bounds_behind_it()
    {
        var window = new MainWindow(
            StoreWith(new WindowBounds(50, 60, 1200, 800, Maximized: true)))
        { DataContext = new MainViewModel() };
        window.Show();

        Assert.Equal(WindowState.Maximized, window.WindowState);
        window.Close();
    }

    [AvaloniaFact]
    public void Unmaximizing_after_a_maximized_restore_lands_on_the_saved_normal_bounds()
    {
        var window = new MainWindow(
            StoreWith(new WindowBounds(50, 60, 1200, 800, Maximized: true)))
        { DataContext = new MainViewModel() };
        window.Show();

        window.WindowState = WindowState.Normal;

        Assert.Equal(1200, window.Width);
        Assert.Equal(800, window.Height);
        window.Close();
    }

    [AvaloniaFact]
    public void No_store_keeps_the_default_shape()
    {
        var window = new MainWindow { DataContext = new MainViewModel() };
        window.Show();

        Assert.Equal(1140, window.Width);
        Assert.Equal(720, window.Height);
        window.Close();
    }

    [AvaloniaFact]
    public void Degenerate_saved_bounds_keep_the_default_shape()
    {
        var window = new MainWindow(
            StoreWith(new WindowBounds(0, 0, 0, 0, Maximized: false)))
        { DataContext = new MainViewModel() };
        window.Show();

        Assert.Equal(1140, window.Width);
        Assert.Equal(720, window.Height);
        window.Close();
    }

    [AvaloniaFact]
    public void Closing_saves_the_current_bounds()
    {
        var store = GuiStateStore.Ephemeral();
        var window = new MainWindow(store)
        { DataContext = new MainViewModel() };
        window.Show();
        window.Width = 1000;
        window.Height = 690;
        window.UpdateLayout();

        window.Close();

        var saved = store.State.Window;
        Assert.NotNull(saved);
        Assert.Equal(1000, saved!.Width);
        Assert.Equal(690, saved.Height);
        Assert.False(saved.Maximized);
    }

    [AvaloniaFact]
    public void Closing_while_maximized_saves_the_flag()
    {
        var store = GuiStateStore.Ephemeral();
        var window = new MainWindow(store)
        { DataContext = new MainViewModel() };
        window.Show();
        window.WindowState = WindowState.Maximized;

        window.Close();

        Assert.True(store.State.Window!.Maximized);
    }
}
