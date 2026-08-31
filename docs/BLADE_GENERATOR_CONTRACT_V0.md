# BLADE — Contrat de générateur V0

Date : 2026-08-31
Statut : SPECIFICATION — aucune implémentation

## 1. But

Définir un contrat unique pour les générateurs BLADE afin qu'un générateur analytique
(`visserie`, `engrenage`, `roulement`, `geo`, `granit`) et un générateur dépendant de
Blender / Geometry Nodes (`escalier`) puissent être décrits, rejoués et contrôlés sans
cas métier particulier dans l'orchestrateur.

Le contrat décrit le générateur ; il ne choisit pas encore la représentation canonique
(recette vs arbre Geometry Nodes).

## 2. Identité obligatoire

Chaque générateur expose un descripteur immuable :

```text
id          : identifiant stable, ASCII, snake_case
famille     : famille fonctionnelle stable
version     : version sémantique du contrat de géométrie
runtime     : pure_python | blender
```

`runtime` est une capacité déclarative, pas une exception de l'orchestrateur : le même
contrat accepte un générateur exécutable hors Blender ou nécessitant Blender.

## 3. Paramètres

Le générateur expose un schéma de paramètres :

```text
paramètres : {
  nom: {
    type,
    unité,
    obligatoire,
    défaut,
    minimum,
    maximum,
    valeurs_autorisées,
    description
  }
}
```

Règles :

- les unités sont explicites ;
- les bornes sont des métadonnées de contrat ;
- un générateur ne doit pas silencieusement remplacer une valeur invalide par une autre ;
- si le contrat autorise une entrée absurde pour tester la robustesse, elle doit rester
  observable et produire un verdict, pas être masquée par un clamp implicite.

## 4. Reproductibilité

Une génération est décrite par une recette minimale :

```text
{
  generator_id,
  generator_version,
  parameters,
  seed
}
```

`seed` vaut `null` lorsqu'aucune stochasticité n'est utilisée.

La recette doit suffire à identifier exactement la demande de génération. Les dépendances
externes éventuelles doivent être déclarées séparément et ne doivent pas être implicites.

## 5. Entrée de génération

Le contrat logique est :

```text
build(params) -> artifact
```

avec :

```text
artifact = {
  handle,
  runtime,
  metadata
}
```

Le `handle` est opaque pour l'orchestrateur. Il peut représenter un maillage en mémoire,
un objet Blender, un node group ou tout autre artefact conforme au runtime déclaré.

L'orchestrateur ne dépend donc ni de `bmesh`, ni de `bpy`, ni de Geometry Nodes.

## 6. Contrôles

Le contrat logique est :

```text
controles(artifact, profil) -> rapport
```

Un rapport contient au minimum :

```text
{
  generator_id,
  generator_version,
  profil,
  verdict,
  criteres: [
    {
      id,
      valeur_lue,
      valeur_attendue,
      tolerance,
      erreur,
      verdict,
      evidence
    }
  ]
}
```

Un contrôle doit relire l'artefact produit. Les valeurs théoriques ne suffisent pas à
elles seules à établir le verdict.

## 7. Séparation génération / contrôle

`build` ne décide pas du verdict QC final.

`controles` ne reconstruit pas silencieusement une autre géométrie pour obtenir ses mesures.

Les contrôles doivent être capables de produire un échec explicable, pas seulement
`True/False`.

## 8. Balayage

Lorsqu'un générateur possède une surface de paramètres importante, il peut exposer :

```text
balayage(cas) -> rapport
```

Le banc reste propriétaire de la sélection des cas. Le générateur peut fournir des cas
représentatifs, mais ne doit pas être l'unique source de son propre oracle.

## 9. Correspondance aux deux cas de référence

### `visserie`

Le module existant fournit une génération analytique en `bmesh`, avec `controle()` et
sans `bpy.ops`. Il correspond naturellement à :

- `runtime = pure_python` dans le contexte où `bmesh` est disponible ;
- paramètres de diamètre, longueur et résolution ;
- `build` = construction du maillage ;
- `controles` = relecture des cotes et du caractère manifold.

Point à normaliser avant implémentation : `bmesh` reste une dépendance d'exécution, même si
le module n'importe pas `bpy`.

### `escalier`

Le module existant construit un `GeometryNodeTree`, le pose sur un objet et relit la
géométrie évaluée. Il correspond naturellement à :

- `runtime = blender` ;
- paramètres Hauteur, Largeur, Giron, Hauteur de marche, Epaisseur, Matériau ;
- `build` = construction/installation du node group ;
- `controles` = évaluation puis mesure de la géométrie.

Le contrat doit donc accepter qu'un artefact soit une structure Blender évaluée. Il ne doit
pas imposer un type d'artefact commun aux deux générateurs.

## 10. Non-décisions

Ne sont volontairement PAS tranchés par cette spécification :

1. recette comme représentation paramétrique canonique ;
2. arbre Geometry Nodes comme représentation paramétrique canonique ;
3. familles retenues pour V1 ;
4. budgets Fab définitifs (triangles, texel density, LOD, etc.).

Ces décisions doivent être documentées séparément avec leurs sources.

## 11. Critère d'acceptation de ce contrat

Le contrat V0 sera considéré valide lorsque `visserie` et `escalier` pourront être décrits
par ce modèle sans branchement spécifique dans l'orchestrateur et sans abandonner leurs
contrôles de géométrie existants.
