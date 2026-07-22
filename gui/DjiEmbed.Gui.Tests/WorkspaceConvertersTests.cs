using System.Globalization;
using DjiEmbed.Gui.Views;

namespace DjiEmbed.Gui.Tests;

public class WorkspaceConvertersTests
{
    [Theory]
    [InlineData(@"C:\Drone\alps-trip", "alps-trip")]
    [InlineData("/home/marcus/footage/", "footage")]
    [InlineData(@"C:\", "C:")]
    [InlineData("/", "/")]
    [InlineData(@"\", @"\")]
    public void FolderLeafName_always_shows_something(
        string path, string expected) =>
        Assert.Equal(expected, WorkspaceConverters.FolderLeafName.Convert(
            path, typeof(string), null, CultureInfo.InvariantCulture));
}
