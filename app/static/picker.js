/* Player search box with its own suggestion list (phones ignore <datalist>).

   <div class="picker" data-mode="multi|single" data-players='[{"id":1,"name":"Ana"}]'
        data-create="➕ Create «{name}»" data-one="{n} player" data-many="{n} players">
     <input class="picker-input">
     <div class="picker-suggestions"></div>
     multi:  <ul class="chips picker-chosen"></ul> <p class="picker-count"></p>
             (each chosen player adds a hidden players=<id>, or new_players=<name>)
     single: <input type="hidden" class="picker-create" name="create">
             (choosing fills the input and submits its form; create=1 for a new name)
   </div>
*/
(function () {
  function norm(text) {
    return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  }

  document.querySelectorAll(".picker").forEach(function (box) {
    var players = JSON.parse(box.dataset.players);
    var multi = box.dataset.mode === "multi";
    var input = box.querySelector(".picker-input");
    var list = box.querySelector(".picker-suggestions");
    var chosen = box.querySelector(".picker-chosen");
    var count = box.querySelector(".picker-count");

    function taken() {
      return chosen ? Array.from(chosen.querySelectorAll("input")).map(function (i) { return i.dataset.key; }) : [];
    }

    function option(text, action, extraClass) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "suggestion" + (extraClass ? " " + extraClass : "");
      b.textContent = text;
      b.addEventListener("click", action);
      list.appendChild(b);
    }

    function render() {
      var q = norm(input.value), name = input.value.trim();
      list.innerHTML = "";
      if (!q) return;
      var used = taken();
      players.filter(function (p) { return norm(p.name).indexOf(q) >= 0 && used.indexOf("id:" + p.id) < 0; })
        .slice(0, 8)
        .forEach(function (p) { option("👤 " + p.name, function () { choose(p); }); });
      var exists = players.some(function (p) { return norm(p.name) === q; });
      if (!exists && used.indexOf("new:" + q) < 0) {
        option(box.dataset.create.replace("{name}", name), function () { choose({name: name}); }, "create");
      }
    }

    function updateCount() {
      if (!count) return;
      var n = chosen.children.length;
      count.textContent = (n === 1 ? box.dataset.one : box.dataset.many).replace("{n}", n);
    }

    function choose(p) {
      if (!multi) {
        input.value = p.name;
        box.querySelector(".picker-create").value = p.id ? "" : "1";
        input.form.submit();
        return;
      }
      var li = document.createElement("li");
      var hidden = document.createElement("input");
      var remove = document.createElement("button");
      hidden.type = "hidden";
      if (p.id) {
        hidden.name = "players"; hidden.value = p.id; hidden.dataset.key = "id:" + p.id;
      } else {
        hidden.name = "new_players"; hidden.value = p.name; hidden.dataset.key = "new:" + norm(p.name);
      }
      remove.type = "button";
      remove.className = "link";
      remove.textContent = "✖️";
      remove.setAttribute("aria-label", "✖️ " + p.name);
      remove.addEventListener("click", function () { li.remove(); updateCount(); });
      li.append((p.id ? "👤 " : "🆕 ") + p.name, hidden, remove);
      chosen.appendChild(li);
      input.value = "";
      list.innerHTML = "";
      input.focus();
      updateCount();
    }

    input.addEventListener("input", render);
    input.addEventListener("keydown", function (e) {
      if (e.key !== "Enter") return;
      e.preventDefault();  // never submit the whole form from the search box
      var first = list.querySelector("button");
      if (first) first.click();
    });
    updateCount();
  });
})();
