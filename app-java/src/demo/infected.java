package demo;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.BufferedReader;
import java.io.InputStreamReader;

public class DemoInfected {
    private static final Logger log = LogManager.getLogger(DemoInfected.class);

    public static void main(String[] args) throws Exception {
        System.out.print("Type something: ");
        String userInput = new BufferedReader(new InputStreamReader(System.in)).readLine();

        // Uso “sospetto”: concatenazione diretta di input non fidato
        // Con lookups attivi, un pattern ${...} può innescare la risoluzione.
        log.error("User message: " + userInput);

        // Variante: anche il logging parametrico può arrivare al resolver in quelle versioni
        log.warn("User message param: {}", userInput);

        System.out.println("Done.");
    }
}
