import unreal

sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
unreal.log_warning(f"SubobjectDataSubsystem: {dir(sub)}")

# Check how to add component or create an actor with HISM
# Alternatively, check creating a Blueprint asset or adding component to Actor in Python
