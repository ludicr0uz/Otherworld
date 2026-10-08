#include "OtherworldNetLibrary.h"

#include "GameFramework/Actor.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(OtherworldNetLibrary)

bool UOtherworldNetLibrary::IsLevelActor(const AActor* Actor)
{
	return Actor != nullptr && Actor->IsNetStartupActor();
}
