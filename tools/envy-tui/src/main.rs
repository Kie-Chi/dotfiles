mod app;
mod backend;
mod model;
mod ui;

use std::{
    io::{self, Stdout},
    sync::mpsc,
    time::Duration,
};

use app::App;
use crossterm::{
    event::{self, Event},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{backend::CrosstermBackend, Terminal};

const POLL_INTERVAL: Duration = Duration::from_millis(80);

fn run_app(terminal: &mut Terminal<CrosstermBackend<Stdout>>) -> io::Result<()> {
    let (tx, rx) = mpsc::channel();
    let mut app = App::new(tx, rx);
    app.load_current(false);
    while !app.should_quit {
        let body_height = terminal.size()?.height.saturating_sub(4);
        app.clamp_scroll(body_height);
        terminal.draw(|frame| ui::draw(frame, &app))?;
        if event::poll(POLL_INTERVAL)? {
            if let Event::Key(key) = event::read()? {
                app.handle_key(key);
            }
        }
        app.receive_messages();
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;
    let result = run_app(&mut terminal);
    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    terminal.show_cursor()?;
    result?;
    Ok(())
}
