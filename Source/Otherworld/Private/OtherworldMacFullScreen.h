#pragma once

namespace OtherworldMacFullScreen
{
	/**
	 * On the Mac, in a game: while the game is in front and in full screen its display
	 * is captured, so the Dock, the menu bar and the hot corners are off it. Nothing
	 * elsewhere. Called once, at the module's startup.
	 */
	void HideDockAndMenuBar();
}
