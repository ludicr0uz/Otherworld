import sys
import time
sys.path.append("/Users/Shared/Epic Games/UE_5.8/Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python")
import remote_execution

remote_exec = remote_execution.RemoteExecution()
remote_exec.start()
time.sleep(1.0)

print("Searching for running Unreal Editor sessions...")
nodes = remote_exec.remote_nodes
print(f"Discovered remote nodes: {nodes}")

if nodes:
    remote_exec.open_command_connection(nodes[0].get("node_id"))
    res = remote_exec.run_command("import unreal; unreal.EditorLoadingAndSavingUtils.reload_packages([unreal.EditorAssetSubsystem().load_asset('/Game/Maps/Lvl_Forest')])")
    print(f"Command result: {res}")
    remote_exec.close_command_connection()
else:
    print("No live Unreal Editor GUI node discovered.")

remote_exec.stop()
