bl_info = {
    "name": "Greenscreen AI Data Prep",
    "author": "Gemini Code Assist",
    "version": (1, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Greenscreen",
    "description": "Initial settings for Greenscreen AI Data Prep project",
    "category": "System",
}

import bpy
import os

class GREENSCREEN_OT_setup(bpy.types.Operator):
    """Configure initial settings for Greenscreen AI Data Prep"""
    bl_idname = "greenscreen.setup_project"
    bl_label = "Initialize Project Settings"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene

        # 1. Set Render Engine to Cycles (Required for indirect_only and holdout nuance)
        scene.render.engine = 'CYCLES'

        # 2. Set Frame Range (Exactly 48 frames per styleguide)
        scene.frame_start = 1
        scene.frame_end = 48

        # 3. Set Resolution to 2048x2048 (Standard for AI datasets)
        scene.render.resolution_x = 2048
        scene.render.resolution_y = 2048
        scene.render.resolution_percentage = 100

        # 4. Set Color Management to Standard
        # This ensures that the green background is rendered as pure (0, 1, 0)
        scene.display_settings.display_device = 'sRGB'
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0

        # 5. Set Output Format to OpenEXR RGBA
        scene.render.image_settings.file_format = 'OPEN_EXR'  # Use OpenEXR for high-bit depth output
        scene.render.image_settings.color_mode = 'RGBA' # Ensure alpha channel is included
        scene.render.image_settings.color_depth = '32' # Use 32-bit for maximum precision in AI data prep
        scene.render.image_settings.quality = 90 # DWAB compression quality
        scene.render.image_settings.exr_codec = 'DWAB'

        # 6. Setup World Background (Pure Green Screen)
        if not scene.world:
            new_world = bpy.data.worlds.new("GreenscreenWorld")
            scene.world = new_world
        
        scene.world.use_nodes = True
        nodes = scene.world.node_tree.nodes
        nodes.clear()
        
        # World Shader Logic: Black for Camera, Gray for Bounce (Neutral Lighting) [cite: 27]
        node_lp = nodes.new(type='ShaderNodeLightPath')
        node_mix = nodes.new(type='ShaderNodeMixShader')
        
        node_bg_camera = nodes.new(type='ShaderNodeBackground')
        node_bg_camera.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0) # Completely Black
        
        node_bg_bounce = nodes.new(type='ShaderNodeBackground')
        node_bg_bounce.inputs[0].default_value = (0.5, 0.5, 0.5, 1.0) # Neutral Gray
        
        node_output = nodes.new(type='ShaderNodeOutputWorld')
        
        links = scene.world.node_tree.links
        links.new(node_lp.outputs['Is Camera Ray'], node_mix.inputs[0])
        links.new(node_bg_bounce.outputs[0], node_mix.inputs[1])
        links.new(node_bg_camera.outputs[0], node_mix.inputs[2])
        links.new(node_mix.outputs[0], node_output.inputs[0])

        # Enable Transparency to ensure Alpha and FG passes work correctly
        scene.render.film_transparent = True

        self.report({'INFO'}, "Greenscreen AI Data Prep settings applied.")
        return {'FINISHED'}

class GREENSCREEN_OT_setup_passes(bpy.types.Operator):
    """Setup render passes and output nodes for export"""
    bl_idname = "greenscreen.setup_passes"
    bl_label = "Setup Render Passes"
    bl_options = {'REGISTER', 'UNDO'}

    def get_layer_collection(self, layer_collection, coll_name):
        """Recursively find a layer collection by name"""
        if layer_collection.name == coll_name:
            return layer_collection
        for child in layer_collection.children:
            found = self.get_layer_collection(child, coll_name)
            if found:
                return found
        return None

    def execute(self, context):
        scene = context.scene

        # 0. Check if file is saved to determine base path
        if not bpy.data.is_saved:
            self.report({'WARNING'}, "Save your .blend file first to enable automatic folder incrementing.")
            return {'CANCELLED'}
        
        # 1. Setup View Layers and Visibility Logic
        view_layer_names = ["ViewLayer", "FG", "BG"]
        for name in view_layer_names:
            if name not in scene.view_layers:
                scene.view_layers.new(name=name)
        
        fg_coll_name = scene.gs_foreground_coll
        bg_coll_name = scene.gs_background_coll

        if not fg_coll_name or not bg_coll_name:
            self.report({'ERROR'}, "Please select both Subject and Environment collections.")
            return {'CANCELLED'}

        # Configure Visibility for each layer
        for vl in scene.view_layers:
            fg_lc = self.get_layer_collection(vl.layer_collection, fg_coll_name)
            bg_lc = self.get_layer_collection(vl.layer_collection, bg_coll_name)
            
            if not fg_lc or not bg_lc: continue

            if vl.name == "ViewLayer": # Input Pass
                fg_lc.exclude = False
                bg_lc.exclude = False
                fg_lc.holdout = False
                bg_lc.holdout = False
            
            elif vl.name == "FG": # FG Pass: Subject on Black
                fg_lc.exclude = False
                bg_lc.indirect_only = True
                bg_lc.holdout = True # Ensure background is hidden from camera
                fg_lc.holdout = False
                
            elif vl.name == "BG": # BG Pass: Backdrop with Shadow
                bg_lc.exclude = False
                fg_lc.indirect_only = True
                fg_lc.holdout = True # Ensure subject is hidden from camera [cite: 15]
                bg_lc.holdout = False

        # 2. Access Compositing Node Group (Blender 5.0 API)
        tree = scene.compositing_node_group
        if tree is None:
            # Initialize a new compositor node group and assign it to the scene
            tree = bpy.data.node_groups.new("CompositingNodeTree", "CompositorNodeTree")
            scene.compositing_node_group = tree
            
        nodes = tree.nodes
        links = tree.links
        nodes.clear()
        
        # 2.1 Define Interface Sockets (Blender 5.0 API)
        tree.interface.clear()
        tree.interface.new_socket(name="Input", in_out='INPUT', socket_type='NodeSocketColor')
        tree.interface.new_socket(name="FG", in_out='INPUT', socket_type='NodeSocketColor')
        tree.interface.new_socket(name="BG", in_out='INPUT', socket_type='NodeSocketColor')
        tree.interface.new_socket(name="Alpha", in_out='INPUT', socket_type='NodeSocketFloat')
        
        # 3. Create Render Layer Nodes for each pass
        rl_input = nodes.new('CompositorNodeRLayers')
        rl_input.layer = "ViewLayer"
        rl_input.location = (0, 400)
        
        rl_fg = nodes.new('CompositorNodeRLayers')
        rl_fg.layer = "FG"
        rl_fg.location = (0, 100)
        
        rl_bg = nodes.new('CompositorNodeRLayers')
        rl_bg.layer = "BG"
        rl_bg.location = (0, -200)
        
        # 3.1 Create Alpha Over for FG Pass (Ensures FG is on Black)
        alpha_over = nodes.new('CompositorNodeAlphaOver')
        alpha_over.location = (300, 150)
        alpha_over.inputs[1].default_value = (0, 0, 0, 1) # Black Background
        links.new(rl_fg.outputs['Alpha'], alpha_over.inputs[0]) # Factor
        links.new(rl_fg.outputs['Image'], alpha_over.inputs[2]) # Foreground
        
        # 4. Determine next Clip folder name (Automatic Increment)
        base_dir = os.path.dirname(bpy.data.filepath)
        target_name = scene.gs_clip_name if scene.gs_clip_name else "Clip0001"
        clip_name = target_name
        
        # If the name follows the Clip#### pattern, increment the number directly
        if target_name.startswith("Clip") and target_name[4:].isdigit():
            padding = len(target_name) - 4
            while os.path.exists(os.path.join(base_dir, clip_name)):
                num = int(clip_name[4:])
                clip_name = f"Clip{num + 1:0{padding}d}"
        else:
            # Standard suffix increment for custom names
            clip_index = 1
            while os.path.exists(os.path.join(base_dir, clip_name)):
                clip_name = f"{target_name}_{clip_index:02d}"
                clip_index += 1
        
        # Physically create the directory structure to avoid render errors
        clip_path = os.path.join(base_dir, clip_name)
        os.makedirs(clip_path, exist_ok=True)

        # 5. Setup Individual File Output Nodes for each directory
        # This ensures the OS-level folder structure is respected in 5.0.1
        passes = [
            ("Input", rl_input.outputs['Image'], (600, 400), "RGBA"),
            ("FG", alpha_over.outputs['Image'], (600, 150), "RGBA"),
            ("BG", rl_bg.outputs['Image'], (600, -100), "RGBA"),
            ("Alpha", rl_fg.outputs['Alpha'], (600, -350), "FLOAT")
        ]

        for pass_name, output_socket, loc, socket_type in passes:
            # Create sub-directory physically
            os.makedirs(os.path.join(clip_path, pass_name), exist_ok=True)
            
            # Create and configure node
            node = nodes.new('CompositorNodeOutputFile')
            node.name = f"Output_{pass_name}"
            node.label = f"Export {pass_name}"
            node.location = loc
            
            # Blender 5.0 API: directory is the folder, file_name is the prefix
            node.directory = f"//{clip_name}/{pass_name}/"
            node.file_name = "render_"
            
            # Set format to OPEN_EXR_MULTILAYER as per your environment's valid list
            node.format.file_format = 'OPEN_EXR_MULTILAYER'
            node.format.exr_codec = 'DWAB'
            node.format.color_depth = '32'
            node.format.color_mode = 'RGBA'
            
            # Blender 5.0 API: Ensure socket_type matches the source data exactly
            # to avoid "Conversion is not supported" errors.
            node.file_output_items.clear()
            node.file_output_items.new(socket_type, name=pass_name)
            
            links.new(output_socket, node.inputs[0])

        self.report({'INFO'}, f"Configured for {clip_name}")
        return {'FINISHED'}

class GREENSCREEN_OT_render_clip(bpy.types.Operator):
    """Trigger the animation render for the current clip"""
    bl_idname = "greenscreen.render_clip"
    bl_label = "Render Animation Clip"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Triggers the render animation (Ctrl+F12)
        bpy.ops.render.render(animation=True)
        self.report({'INFO'}, "Render started. Check the Clip folder for output.")
        return {'FINISHED'}

class GREENSCREEN_PT_panel(bpy.types.Panel):
    """Panel for Greenscreen AI Data Prep"""
    bl_label = "Greenscreen AI Data Prep"
    bl_idname = "GREENSCREEN_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Greenscreen'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="Project Configuration")
        layout.prop(scene, "gs_clip_name")
        layout.prop_search(scene, "gs_foreground_coll", bpy.data, "collections", text="Subject")
        layout.prop_search(scene, "gs_background_coll", bpy.data, "collections", text="Environment")
        layout.separator()
        layout.label(text="Project Initialization")
        layout.operator("greenscreen.setup_project", icon='PREFERENCES')
        layout.separator()
        layout.label(text="Export Configuration")
        layout.operator("greenscreen.setup_passes", icon='RENDER_RESULT')
        layout.separator()
        layout.label(text="Execution")
        layout.operator("greenscreen.render_clip", icon='RENDER_ANIMATION')

def register():
    bpy.utils.register_class(GREENSCREEN_OT_setup)
    bpy.utils.register_class(GREENSCREEN_OT_setup_passes)
    bpy.utils.register_class(GREENSCREEN_OT_render_clip)
    bpy.utils.register_class(GREENSCREEN_PT_panel)
    
    # Register Scene properties for collection selection and clip naming
    bpy.types.Scene.gs_foreground_coll = bpy.props.StringProperty(
        name="Subject Collection",
        description="Collection containing the foreground subject"
    )
    bpy.types.Scene.gs_background_coll = bpy.props.StringProperty(
        name="Environment Collection",
        description="Collection containing the greenscreen/studio background"
    )
    bpy.types.Scene.gs_clip_name = bpy.props.StringProperty(
        name="Clip Name",
        description="Name of the export folder",
        default="Clip0001"
    )

def unregister():
    bpy.utils.unregister_class(GREENSCREEN_OT_setup)
    bpy.utils.unregister_class(GREENSCREEN_OT_setup_passes)
    bpy.utils.unregister_class(GREENSCREEN_OT_render_clip)
    bpy.utils.unregister_class(GREENSCREEN_PT_panel)
    
    del bpy.types.Scene.gs_foreground_coll
    del bpy.types.Scene.gs_background_coll
    del bpy.types.Scene.gs_clip_name

if __name__ == "__main__":
    register()
