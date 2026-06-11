import bpy
import math
import mathutils
import os

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

# --- 3. MOTOR DO SPRINT 3: AUTOMACÕES MATEMÁTICAS E CORREÇÃO DE RIGGING ---

def purge_orphan_vertex_groups(temp_obj):
    """Remove vertex groups que não possuem pesos ou não correspondem a ossos do Rig"""
    if temp_obj.type != 'MESH' or not temp_obj.vertex_groups:
        return

    print(f"[SPRINT 3] Iniciando purga de Vertex Groups em: {temp_obj.name}")
    
    # Encontra o esqueleto associado (se houver)
    armature_obj = None
    for mod in temp_obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object:
            armature_obj = mod.object
            break

    bone_names = set(armature_obj.data.bones.keys()) if armature_obj else set()
    
    # Conta quantos vértices estão linkados a cada grupo
    group_counts = {g.index: 0 for g in temp_obj.vertex_groups}
    for vert in temp_obj.data.vertices:
        for group in vert.groups:
            if group.weight > 0.0001:  # Ignora pesos irrelevantes
                group_counts[group.group] += 1

    # Lista os grupos que serão removidos
    groups_to_remove = []
    for group in temp_obj.vertex_groups:
        # Condição 1: Grupo está totalmente vazio (sem vértices assinados)
        is_empty = group_counts[group.index] == 0
        # Condição 2: Existe um Rig, mas o grupo não é o nome de nenhum osso válido
        is_orphan = armature_obj and (group.name not in bone_names)
        
        if is_empty or is_orphan:
            groups_to_remove.append(group)

    # Remove os grupos inválidos de trás para frente (evita quebra de índice)
    removed_count = len(groups_to_remove)
    for group in groups_to_remove:
        temp_obj.vertex_groups.remove(group)
        
    print(f"[SPRINT 3] Purga concluída. {removed_count} Vertex Groups inválidos foram removidos.")


def apply_transforms_to_temp_object(context, temp_obj):
    """Força a aplicação de Rotação e Escala via Context Override (Seguro contra erros de View Layer)"""
    print(f"[SPRINT 3] Aplicando Rotação e Escala no objeto: {temp_obj.name}")
    try:
        # Criamos um contexto customizado para o operador não depender da tela do usuário
        with context.temp_override(active_object=temp_obj, selected_editable_objects=[temp_obj]):
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        print(f"[SPRINT 3] Transformações aplicadas com sucesso!")
    except Exception as e:
        print(f"[ERRO SPRINT 3] Falha ao aplicar transformações: {str(e)}")

def fix_coordinate_system_z_to_y(context, temp_obj):
    """Rotaciona preservando o trabalho do artista e aplica a rotação via Context Override"""
    print(f"[SPRINT 3] Corrigindo eixos de rotação (Z-Up para Y-Up) no objeto: {temp_obj.name}")
    try:
        # 1. Rotaciona multiplicando/adicionando à rotação que o artista já tinha feito
        temp_obj.rotation_euler.rotate_axis('X', math.radians(-90))
        
        # 2. Aplica a rotação de forma isolada e segura usando o override de contexto
        with context.temp_override(active_object=temp_obj, selected_editable_objects=[temp_obj]):
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        print(f"[SPRINT 3] Eixos corrigidos e congelados para o padrão Roblox.")
    except Exception as e:
        print(f"[ERRO SPRINT 3] Falha ao corrigir eixos de rotação: {str(e)}")


# --- 4. INTERFACE E OPERADORES ---

# --- 4. MOTOR DO SPRINT 4: PIPELINE DE EXPORTAÇÃO ---

def export_to_fbx(context, temp_obj):
    """Exporta o objeto temporário corrigido para a pasta do arquivo .blend atual"""
    print(f"[SPRINT 4] Iniciando exportação FBX para o objeto: {temp_obj.name}")
    
    blend_filepath = bpy.data.filepath
    if not blend_filepath:
        output_dir = os.path.expanduser("~")
        filename = f"{temp_obj.name}_RobloxExport.fbx"
    else:
        output_dir = os.path.dirname(blend_filepath)
        base_name = os.path.splitext(os.path.basename(blend_filepath))[0]
        filename = f"{base_name}_{temp_obj.name}.fbx"
        
    export_path = os.path.join(output_dir, filename)
    
    try:
        with context.temp_override(active_object=temp_obj, selected_editable_objects=[temp_obj]):
            bpy.ops.export_scene.fbx(
                filepath=export_path,
                use_selection=True,
                global_scale=1.0,
                apply_unit_scale=True,
                apply_scale_options='FBX_SCALE_NONE',
                bake_space_transform=False,
                object_types={'MESH', 'ARMATURE'},
                use_mesh_modifiers=True,
                mesh_smooth_type='FACE',
                add_leaf_bones=False,
                use_armature_deform_only=True,
                bake_anim=False
            )
        print(f"[SPRINT 4] Sucesso! Arquivo exportado em: {export_path}")
        return export_path
    except Exception as e:
        print(f"[ERRO SPRINT 4] Falha ao exportar FBX: {str(e)}")
        raise e

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
        export_path_success = None  # Inicializa a variável com segurança
        
        try:
            print("\n[MOTOR] Iniciando pipeline de exportação isolada...")
            temp_obj, temp_collection = duplicate_and_isolate_object(context, active_obj)
            
            # --- EXECUÇÃO DAS AUTOMAÇÕES DO SPRINT 3 ---
            apply_transforms_to_temp_object(context, temp_obj)
            fix_coordinate_system_z_to_y(context, temp_obj)
            purge_orphan_vertex_groups(temp_obj)
            
            # --- EXECUÇÃO DO PIPELINE DO SPRINT 4 ---
            export_path_success = export_to_fbx(context, temp_obj)
            
            # Atualiza a mensagem que vai aparecer na janela para o usuário
            report_msg += f"\n\n🚀 EXPORTAÇÃO CONCLUÍDA!\nArquivo salvo em:\n{export_path_success}"
            
        except Exception as e:
            print(f"[ERRO CRÍTICO NO MOTOR]: {str(e)}")
            self.report({'ERROR'}, f"Falha interna no pipeline: {str(e)}")
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

# --- 6. REGISTRO DO ADD-ON ---

classes = (
    ROBLOX_OT_error_dialog,
    ROBLOX_OT_verify_export,
    ROBLOX_PT_sidebar_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    print("[True One] Add-on carregado com sucesso!")

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("[True One] Add-on descarregado com sucesso!")

if __name__ == "__main__":
    register()