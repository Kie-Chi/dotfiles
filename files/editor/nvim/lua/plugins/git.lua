return {
  {
    'TimUntersberger/neogit',
    dependencies = {
      'nvim-lua/plenary.nvim',
      'sindrets/diffview.nvim',
    },
    opts = {
      signs = {
        section = { "▶", "▼" },
        item = { "▶", "▼" },
        hunk = { "", "" },
      }
    },
    lazy = true,
    cmd = 'Neogit',
    keys = {
      {"<leader>g", "<cmd>Neogit<cr>"},
    },
  },

  {
    'APZelos/blamer.nvim',
    cmd = { 'BlamerHide', 'BlamerShow', 'BlamerToggle' },
  },
}
