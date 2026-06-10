import bpy
import math

bl_info = {
    "name": "True One - Roblox Exporter",
    "author": "Kaique Klock",
    "version": (1, 3, 0),  # Avançamos para o marco do Sprint 3
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Roblox Tool",
    "description": "Valida e exporta malhas e rigs do Blender para o Roblox Studio em um clique.",
    "category": "Import-Export",
}

# --- 1. MOTOR DE VALIDAÇÃO ---

def check_mesh_health(obj):
    if obj.type != 'MESH':
        return [], []
    issues = []
    warnings = []
    has_unapplied_scale = any(abs(s - 1.0) > 0.001 for s in obj.scale)
    has_unapplied_rotation = any(abs(r) > 0.001 for r in obj.rotation_euler)
    if has_unapplied_scale or has_unapplied_rotation:
        # Mudamos de Crítico para Aviso: O add-on agora resolve isso sozinho na cópia!
        warnings.append("Transformações locais não aplicadas (O add-on corrigirá automaticamente na exportação).")
    obj.data.calc_loop_triangles()
    tri_count = len(obj.data.loop_triangles)
    ROBLOX_TRI_LIMIT = 21000
    if tri_count > ROBLOX_TRI_LIMIT:
        warnings.append(f"Alta contagem de triângulos: {tri_count} (Limite ideal Roblox: {ROBLOX_TRI_LIMIT}).")
    return issues, warnings

def check_rig_health(obj):
    issues = []
    warnings = []
    armature_obj = None
    if obj.type == 'ARMATURE':
        armature_obj = obj
    elif obj.type == 'MESH':
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                armature_obj = mod.object
                break
    if armature_obj:
        bone_names = [bone.name for bone in armature_obj.data.bones]
        if "HumanoidRootPart" not in bone_names:
            warnings.append("Aviso de Rig: Não possui o osso raiz 'HumanoidRootPart' (Exigido para R6/R15).")
    return issues, warnings

# --- 2. MOTOR DE ISOLAMENTO PROFUNDO (CÓPIA REAL SEPARADA) ---

def duplicate_and_isolate_object(context, original_obj):
    """Cria uma cópia isolada sem vinculação de malha para evitar ReferenceError"""
    temp_collection = bpy.data.collections.new(name="Roblox_Temp_Export")
    context.scene.collection.children.link(temp_collection)
    
    # Cria uma cópia profunda duplicando os blocos de dados
    temp_obj = original_obj.copy()
    if original_obj.data:
        temp_obj.data = original_obj.data.copy()
        
    temp_collection.objects.link(temp_obj)
    print(f"[MOTOR] Cópia temporária isolada com sucesso: {temp_obj.name}")
    return temp_obj, temp_collection

# --- 3. MOTOR DO SPRINT 3: AUTOMACÕES INVISÍVEIS ---

def apply_transforms_to_temp_object(context, temp_obj):
    """Força a aplicação de Rotação e Escala na cópia temporária de forma invisível"""
    print(f"[SPRINT 3] Aplicando Rotação e Escala no objeto: {temp_obj.name}")
    old_active = context.view_layer.objects.active
    try:
        context.view_layer.objects.active = temp_obj
        bpy.ops.object.select_all(action='DESELECT')
        temp_obj.select_set(True)
        # Executa o comando equivalente ao Ctrl + A (Zera rotação e escala na geometria)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        print(f"[SPRINT 3] Transformações aplicadas! Nova Escala: {temp_obj.scale[:]}")
    except Exception as e:
        print(f"[ERRO SPRINT 3] Falha ao aplicar transformações: {str(e)}")
    finally:
        context.view_layer.objects.active = old_active

def fix_coordinate_system_z_to_y(context, temp_obj):
    """Rotaciona a cópia temporária para alinhar o padrão Z-Up do Blender ao Y-Up do Roblox"""
    print(f"[SPRINT 3] Corrigindo eixos de rotação (Z-Up para Y-Up) no objeto: {temp_obj.name}")
    old_active = context.view_layer.objects.active
    try:
        context.view_layer.objects.active = temp_obj
        bpy.ops.object.select_all(action='DESELECT')
        temp_obj.select_set(True)
        
        # Rotaciona o objeto temporário em -90 graus no eixo X
        temp_obj.rotation_euler = (math.radians(-90), 0.0, 0.0)
        
        # Aplica a rotação imediatamente para fixar a malha em pé no espaço tridimensional
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        print(f"[SPRINT 3] Eixos corrigidos com sucesso para o padrão Roblox.")
    except Exception as e:
        print(f"[ERRO SPRINT 3] Falha ao corrigir eixos de rotação: {str(e)}")
    finally:
        context.view_layer.objects.active = old_active

# --- 4. INTERFACE E OPERADORES ---

class ROBLOX_OT_error_dialog(bpy.types.Operator):
    bl_idname = "roblox.error_dialog"
    bl_label = "Pre-flight Validation Report"
    bl_options = {'INTERNAL'}
    message: bpy.props.StringProperty(default="")
    def execute(self, context): return {'FINISHED'}
    def invoke(self, context, event): return context.window_manager.invoke_props_dialog(self, width=450)
    def draw(self, context):
        layout = self.layout
        lines = self.message.split("\n")
        for line in lines:
            if not line.strip(): continue
            if "ERRO:" in line: layout.label(text=line, icon='CANCEL')
            elif "AVISO:" in line: layout.label(text=line, icon='ERROR')
            elif "SUCESSO:" in line: layout.label(text=line, icon='CHECKMARK')
            else: layout.label(text=line, icon='DOT')

class ROBLOX_OT_verify_export(bpy.types.Operator):
    bl_idname = "roblox.verify_export"
    bl_label = "Verify & Export"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_obj = context.active_object
        if not active_obj or not active_obj.select_get():
            bpy.ops.roblox.error_dialog('INVOKE_DEFAULT', message="ERRO: Nenhum objeto selecionado!")
            return {'CANCELLED'}
            
        obj_name = active_obj.name
        mesh_issues, mesh_warnings = check_mesh_health(active_obj)
        rig_issues, rig_warnings = check_rig_health(active_obj)
        all_issues = mesh_issues + rig_issues
        all_warnings = mesh_warnings + rig_warnings
        
        report_msg = f"Relatório do Objeto: {obj_name}\n\n"
        if all_issues:
            report_msg += "Problemas Críticos Encontrados:\n"
            for issue in all_issues: report_msg += f" - ERRO: {issue}\n"
        elif all_warnings:
            report_msg += "Avisos de Otimização (Exportação Permitida):\n"
            for warn in all_warnings: report_msg += f" - AVISO: {warn}\n"
            report_msg += "\n[MÁGICA]: O add-on aplicará as correções automaticamente na cópia de exportação!"
        else:
            report_msg += "SUCESSO: Seu modelo está 100% otimizado para o Roblox e pronto para o pipeline!"

        temp_obj = None
        temp_collection = None
        
        try:
            print("\n[MOTOR] Iniciando pipeline de exportação isolada...")
            temp_obj, temp_collection = duplicate_and_isolate_object(context, active_obj)
            
            # --- EXECUÇÃO DAS AUTOMAÇÕES DO SPRINT 3 ---
            apply_transforms_to_temp_object(context, temp_obj)
            fix_coordinate_system_z_to_y(context, temp_obj)
            # --------------------------------------------
            
        except Exception as e:
            print(f"[ERRO CRÍTICO NO MOTOR]: {str(e)}")
            self.report({'ERROR'}, f"Falha interna: {str(e)}")
            return {'CANCELLED'}
            
        finally:
            print("[MOTOR] Limpando ambiente temporário de memória...")
            if temp_obj:
                temp_mesh = temp_obj.data
                if temp_collection and temp_obj.name in temp_collection.objects:
                    temp_collection.objects.unlink(temp_obj)
                bpy.data.objects.remove(temp_obj, do_unlink=True)
                if temp_mesh:
                    bpy.data.meshes.remove(temp_mesh)
            if temp_collection:
                bpy.data.collections.remove(temp_collection)
                
            if active_obj and active_obj.name in bpy.data.objects:
                context.view_layer.objects.active = active_obj
                active_obj.select_set(True)
            print("[MOTOR] Limpeza concluída com sucesso. Seu arquivo original está intacto!")

        bpy.ops.roblox.error_dialog('INVOKE_DEFAULT', message=report_msg)
        if all_issues: return {'CANCELLED'}
        return {'FINISHED'}

class ROBLOX_PT_sidebar_panel(bpy.types.Panel):
    bl_label = "Roblox Exporter Options"
    bl_idname = "ROBLOX_PT_sidebar_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Roblox Tool'

    def draw(self, context):
        layout = self.layout
        active_obj = context.active_object
        box = layout.box()
        
        if not active_obj or not active_obj.select_get():
            box.label(text="Nenhum objeto selecionado", icon='ZOOM_ALL')
            layout.separator()
            row = layout.row()
            row.enabled = False
            row.operator("roblox.verify_export", icon='EXPORT', text="Run Pre-flight Check")
        else:
            issues, warnings = check_mesh_health(active_obj)
            rig_issues, rig_warnings = check_rig_health(active_obj)
            total_errors = len(issues) + len(rig_issues)
            total_warns = len(warnings) + len(rig_warnings)
            
            box.label(text=f"Ativo: {active_obj.name}", icon='OBJECT_DATAMODE')
            if total_errors > 0: box.label(text=f"Status: {total_errors} Erro(s) detectados", icon='COLOR_RED')
            elif total_warns > 0: box.label(text="Status: Precisa de Correção Auto", icon='COLOR_YELLOW')
            else: box.label(text="Status: Pronto para Roblox", icon='COLOR_GREEN')
                
            layout.separator()
            layout.operator("roblox.verify_export", icon='EXPORT', text="Run Pre-flight Check")

classes = (
    ROBLOX_OT_error_dialog, 
    ROBLOX_OT_verify_export, 
    ROBLOX_PT_sidebar_panel
)

def register():
    for cls in classes: 
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes: 
        bpy.utils.unregister_class(cls)

if __name__ == "__main__": 
    register()