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
    event::{
        self, DisableBracketedPaste, DisableMouseCapture, EnableBracketedPaste, EnableMouseCapture,
        Event,
    },
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
        let body_height = terminal
            .size()?
            .height
            .saturating_sub(4)
            .saturating_sub(app.input_bar_height());
        app.clamp_scroll(body_height);
        terminal.draw(|frame| ui::draw(frame, &mut app))?;
        if event::poll(POLL_INTERVAL)? {
            match event::read()? {
                Event::Key(key) => app.handle_key(key),
                Event::Mouse(mouse) => app.handle_mouse(mouse),
                Event::Paste(value) => app.handle_paste(&value),
                _ => {}
            }
        }
        app.receive_messages();
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(
        stdout,
        EnterAlternateScreen,
        EnableMouseCapture,
        EnableBracketedPaste
    )?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;
    let result = run_app(&mut terminal);
    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        DisableBracketedPaste,
        DisableMouseCapture,
        LeaveAlternateScreen
    )?;
    terminal.show_cursor()?;
    result?;
    Ok(())
}
