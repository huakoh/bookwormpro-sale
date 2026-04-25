# nix/tui.nix — BookwormPRO TUI (Ink/React) compiled with tsc and bundled
{ pkgs, hermesNpmLib, ... }:
let
  src = ../ui-tui;
  npmDeps = pkgs.fetchNpmDeps {
    inherit src;
    hash = "sha256-RU4qSHgJPMyfRSEJDzkG4+MReDZDc6QbTD2wisa5QE0=";
  };

  npm = hermesNpmLib.mkNpmPassthru { folder = "ui-tui"; attr = "tui"; pname = "bookworm-tui"; };

  packageJson = builtins.fromJSON (builtins.readFile (src + "/package.json"));
  version = packageJson.version;
in
pkgs.buildNpmPackage (npm // {
  pname = "bookworm-tui";
  inherit src npmDeps version;

  doCheck = false;

  installPhase = ''
    runHook preInstall

    mkdir -p $out/lib/bookworm-tui

    cp -r dist $out/lib/bookworm-tui/dist

    # runtime node_modules
    cp -r node_modules $out/lib/bookworm-tui/node_modules

    # @bookworm/ink is a file: dependency, we need to copy it in fr
    rm -f $out/lib/bookworm-tui/node_modules/@bookworm/ink
    cp -r packages/bookworm-ink $out/lib/bookworm-tui/node_modules/@bookworm/ink

    # package.json needed for "type": "module" resolution
    cp package.json $out/lib/bookworm-tui/

    runHook postInstall
  '';
})
