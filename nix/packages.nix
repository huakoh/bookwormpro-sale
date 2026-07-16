# nix/packages.nix — BookwormPRO package built with uv2nix
{ inputs, ... }:
{
  perSystem =
    { pkgs, inputs', ... }:
    let
      hermesVenv = pkgs.callPackage ./python.nix {
        inherit (inputs) uv2nix pyproject-nix pyproject-build-systems;
      };

      hermesNpmLib = pkgs.callPackage ./lib.nix {
        npm-lockfile-fix = inputs'.npm-lockfile-fix.packages.default;
      };

      hermesTui = pkgs.callPackage ./tui.nix {
        inherit hermesNpmLib;
      };

      # Import bundled skills, excluding runtime caches
      bundledSkills = pkgs.lib.cleanSourceWith {
        src = ../skills;
        filter = path: _type: !(pkgs.lib.hasInfix "/index-cache/" path);
      };

      hermesWeb = pkgs.callPackage ./web.nix {
        inherit hermesNpmLib;
      };

      runtimeDeps = with pkgs; [
        nodejs_22
        ripgrep
        git
        openssh
        ffmpeg
        tirith
      ];

      runtimePath = pkgs.lib.makeBinPath runtimeDeps;

      # Lockfile hashes for dev shell stamps
      pyprojectHash = builtins.hashString "sha256" (builtins.readFile ../pyproject.toml);
      uvLockHash =
        if builtins.pathExists ../uv.lock then
          builtins.hashString "sha256" (builtins.readFile ../uv.lock)
        else
          "none";
    in
    {
      packages = {
        default = pkgs.stdenv.mkDerivation {
          pname = "bookwormpro";
          version = (fromTOML (builtins.readFile ../pyproject.toml)).project.version;

          dontUnpack = true;
          dontBuild = true;
          nativeBuildInputs = [ pkgs.makeWrapper ];

          installPhase = ''
            runHook preInstall

            mkdir -p $out/share/bookwormpro $out/bin
            cp -r ${bundledSkills} $out/share/bookwormpro/skills
            cp -r ${hermesWeb} $out/share/bookwormpro/web_dist

            # copy pre-built TUI (same layout as dev: ui-tui/dist/ + node_modules/)
            mkdir -p $out/ui-tui
            cp -r ${hermesTui}/lib/bookworm-tui/* $out/ui-tui/

            ${pkgs.lib.concatMapStringsSep "\n"
              (name: ''
                makeWrapper ${hermesVenv}/bin/${name} $out/bin/${name} \
                  --suffix PATH : "${runtimePath}" \
                  --set BOOKWORMPRO_BUNDLED_SKILLS $out/share/bookwormpro/skills \
                  --set BOOKWORMPRO_WEB_DIST $out/share/bookwormpro/web_dist \
                  --set BOOKWORMPRO_TUI_DIR $out/ui-tui \
                  --set BOOKWORMPRO_PYTHON ${hermesVenv}/bin/python3 \
                  --set BOOKWORMPRO_NODE ${pkgs.nodejs_22}/bin/node
              '')
              [
                "bookworm"
                "bookwormpro"
                "bookworm-acp"
              ]
            }

            runHook postInstall
          '';

          passthru.devShellHook = ''
            STAMP=".nix-stamps/bookwormpro"
            STAMP_VALUE="${pyprojectHash}:${uvLockHash}"
            if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$STAMP_VALUE" ]; then
              echo "bookwormpro: installing Python dependencies..."
              uv venv .venv --python ${pkgs.python312}/bin/python3 2>/dev/null || true
              source .venv/bin/activate
              uv pip install -e ".[all]"
              [ -d mini-swe-agent ] && uv pip install -e ./mini-swe-agent 2>/dev/null || true
              [ -d tinker-atropos ] && uv pip install -e ./tinker-atropos 2>/dev/null || true
              mkdir -p .nix-stamps
              echo "$STAMP_VALUE" > "$STAMP"
            else
              source .venv/bin/activate
              export BOOKWORMPRO_PYTHON=${hermesVenv}/bin/python3
            fi
          '';

          meta = with pkgs.lib; {
            description = "AI agent with advanced tool-calling capabilities";
            homepage = "https://github.com/huakoh/BookwormPRO";
            mainProgram = "bookworm";
            license = licenses.mit;
            platforms = platforms.unix;
          };
        };

        tui = hermesTui;
        web = hermesWeb;

        fix-lockfiles = hermesNpmLib.mkFixLockfiles {
          packages = [ hermesTui hermesWeb ];
        };
      };
    };
}
