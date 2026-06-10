# 🚀 True One - Roblox Exporter (Blender Add-on)

[![Blender Version](https://shields.io)](https://blender.org)
[![Language](https://shields.io)](https://python.org)
[![License](https://shields.io)](LICENSE)

O **True One - Roblox Exporter** é um add-on de código aberto para o Blender desenvolvido em Python. Seu objetivo principal é eliminar o atrito, o retrabalho e os erros manuais que artistas 3D e desenvolvedores enfrentam ao exportar malhas (com e sem rigging) do Blender para o Roblox Studio.

A ferramenta automatiza tarefas complexas e destrutivas em uma **cópia profunda temporária em memória**, garantindo que o arquivo de trabalho original do artista permaneça 100% intacto.

---

## 🎯 O Problema & A Solução

### Principais Dores do Fluxo Tradicional:
* **Eixos Invertidos:** O Blender utiliza o sistema de coordenadas *Z-Up*, enquanto o Roblox utiliza *Y-Up*. Sem tratamento, personagens importados entram "tombados".
* **Transformações Não Aplicadas:** Escalas e rotações locais desalinhadas causam deformações severas e quebras nas animações dentro da engine.
* **Erros de Rigging:** Grupos de vértices vazios (pesos órfãos) provocam rejeição imediata do modelo no importador do Roblox.
* **Refugo Manual:** Perda de tempo limpando, aplicando modificadores e corrigindo o modelo a cada nova iteração.

### A Abordagem "True One" (Zero Ação Manual):
O usuário precisa apenas modelar ou aplicar o rig. Ao clicar em **Run Pre-flight Check**, o add-on assume o pipeline: valida a saúde da malha, isola os dados na memória, aplica as correções necessárias e exporta. Tudo em um único clique.

---

## 🛠️ Arquitetura Técnica & Decisões de Engenharia

Para manter o add-on leve e de fácil instalação, o projeto adota uma filosofia de **zero dependências externas complexas**, utilizando exclusivamente a API nativa do Blender (`bpy`) e módulos padrão do Python.

* **Motor de Isolamento Profundo (Anti-Memory Leak):** Durante o desenvolvimento, mitigamos erros críticos de referência (`ReferenceError: StructRNA removed`). A solução foi reestruturar o pipeline para realizar a varredura de dados *antes* do ciclo de vida em memória e implementar uma duplicação profunda de blocos de dados (`original_obj.data.copy()`), separando completamente as dependências de malha.
* **Gerenciamento de Contexto Seguro:** Utilização rigorosa do bloco `try/finally`. Mesmo que ocorra uma falha crítica no meio do processo, o estado da cena original do usuário é restaurado e todas as coleções ou objetos fantasmas clonados são expurgados da memória RAM.
* **Validação em Tempo Real:** Conversão geométrica da malha para loops de triângulos para antecipar a contagem exata que o motor gráfico do Roblox interpretará (alertando o limite clássico de 21.000 triângulos).

---

## 📌 Cronograma de Desenvolvimento (Sprints)

- [x] **Sprint 1: Fundação & Interface (UI)**
  - Metadados universais e registro na categoria `Import-Export`.
  - Painel lateral dinâmico (**Roblox Tool**) na View3D.
  - Bloqueio inteligente do operador gráfico caso não haja seleção real na cena.
- [x] **Sprint 2: Motor de Isolamento & Pre-flight Check**
  - Sistema de clonagem profunda e isolamento em coleção temporária.
  - Varredura de integridade (transformações, triângulos e presença de `HumanoidRootPart`).
  - Interface adaptativa de diálogos flutuantes para relatórios de Erro, Aviso e Sucesso.
- [ ] **Sprint 3: Automações Matemáticas e Correção de Rigging** *(Próxima Fase)*
  - Aplicação automática invisível de Escala e Rotação.
  - Transmutação de coordenadas matriciais (Z-Up para Y-Up).
  - Purga automatizada de grupos de vértices órfãos.
- [ ] **Sprint 4: Pipeline de Exportação & Polimento**
  - Integração com `bpy.ops.export_scene` nativo.
  - Homologação de importação direta no Roblox Studio.

---

## 🔧 Como Instalar e Testar (Para Desenvolvedores)

### Modo de Desenvolvimento (Recomendado)
Para contribuir ou testar alterações em tempo real sem precisar zipar o projeto:
1. Clone este repositório em uma pasta de sua preferência.
2. Crie um link simbólico (atalho de sistema) da subpasta `roblox_exporter` para a pasta de add-ons do seu Blender (ex: AppData no Windows).
3. No Blender, vá em **Edit > Preferences > Add-ons** e ative o **True One - Roblox Exporter**.
4. Para atualizar o add-on após modificar o código, basta apertar `F3` no Blender e executar `Reload Scripts`.

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

 desenvolvido com 💻 por [Kaique Klock](https://github.com)
