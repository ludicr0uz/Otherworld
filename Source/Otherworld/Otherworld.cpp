#include "CoreTypes.h"
#include "Modules/ModuleManager.h"
#include "OtherworldMacFullScreen.h"

class FOtherworldModule : public FDefaultGameModuleImpl
{
	virtual void StartupModule() override
	{
		OtherworldMacFullScreen::HideDockAndMenuBar();
	}
};

IMPLEMENT_PRIMARY_GAME_MODULE(FOtherworldModule, Otherworld, "Otherworld");
